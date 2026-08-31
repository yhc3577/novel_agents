"""开书大纲服务（D13）：大纲读取 + 生成/覆盖，写图与 open_book 任务共用的单点真相。

- project_outline：卷 → 章 → 细纲 的读取视图，兼容两种 beats 形状（开书写入 / 拆文导入）。
- generate_outline：LLM（high 档）或 demo stub 生成第一卷细纲并落库；force=True 覆盖重生成。
  写图的 ensure_outline 与 open_book 任务都走这里，保证大纲生成逻辑只有一份。
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graphs.ctx import GraphRuntime
from app.graphs.stub import stub_outline
from app.llm.contracts import OutputContract
from app.llm.retry import generate_checked
from app.models import OutlineChapter, Project, Setting, Volume
from app.schemas.writing import OutlineBeats
from app.services.prompt_registry import PromptRegistry


async def outline_count(db: AsyncSession, project_id: int) -> int:
    """项目大纲总章数（跨卷取最大 chapter_no；无卷返回 0）。"""
    vids = list((await db.scalars(select(Volume.id).where(Volume.project_id == project_id))).all())
    if not vids:
        return 0
    last = await db.scalar(
        select(OutlineChapter.chapter_no)
        .where(OutlineChapter.volume_id.in_(vids))
        .order_by(OutlineChapter.chapter_no.desc())
        .limit(1)
    )
    return last or 0


async def project_text(db: AsyncSession, project_id: int) -> str:
    """项目设定串（标题+题材/平台+设定行），与写图 prepare 的 project_text 等价。"""
    project = await db.get(Project, project_id)
    if project is None:
        return ""
    rows = (await db.scalars(select(Setting).where(Setting.project_id == project_id))).all()
    settings = "；".join(f"{s.kind}/{s.title}：{s.content}" for s in rows if s.content)
    return f"{project.title}（{project.genre or ''}/{project.platform or ''}）\n{settings}"


def _normalize_beats(beats: dict | None) -> dict:
    """归一化两种已存在形状：开书写入 {chapter_no,title,summary,target_wordcount} 与
    拆文导入 {summary, beats:[...]} → 统一输出 {summary, target_wordcount, points}。"""
    if not beats:
        return {"summary": "", "target_wordcount": None, "points": []}
    points = beats["beats"] if isinstance(beats.get("beats"), list) else []
    return {
        "summary": beats.get("summary", ""),
        "target_wordcount": beats.get("target_wordcount"),
        "points": points,
    }


async def project_outline(db: AsyncSession, project_id: int) -> dict:
    """读取项目大纲视图（供 GET /projects/{pid}/outline）。"""
    volumes = []
    vols = (
        await db.scalars(select(Volume).where(Volume.project_id == project_id).order_by(Volume.no))
    ).all()
    for v in vols:
        ocs = (
            await db.scalars(
                select(OutlineChapter)
                .where(OutlineChapter.volume_id == v.id)
                .order_by(OutlineChapter.chapter_no)
            )
        ).all()
        chapters = [
            {
                "chapter_no": c.chapter_no,
                "title": c.title,
                "contract_status": c.contract_status,
                "beats": _normalize_beats(c.beats),
            }
            for c in ocs
        ]
        volumes.append({"no": v.no, "title": v.title, "synopsis": v.synopsis, "chapters": chapters})
    return {"has_outline": any(vol["chapters"] for vol in volumes), "volumes": volumes}


async def _delete_outline(db: AsyncSession, project_id: int) -> None:
    """删旧大纲（大纲章节挂在卷下，先删章节再删卷；flush 让删除先于新卷插入生效）。"""
    vids = list((await db.scalars(select(Volume.id).where(Volume.project_id == project_id))).all())
    if vids:
        await db.execute(delete(OutlineChapter).where(OutlineChapter.volume_id.in_(vids)))
    await db.execute(delete(Volume).where(Volume.project_id == project_id))
    await db.flush()


async def generate_outline(
    db: AsyncSession,
    runtime: GraphRuntime,
    *,
    project_id: int,
    scenario: str = "",
    force: bool = False,
) -> int:
    """生成（或覆盖）第一卷开书大纲。已存在且非 force → 静默跳过（与写图历史行为一致）。返回总章数。"""
    if await outline_count(db, project_id) > 0 and not force:
        return await outline_count(db, project_id)
    if force:
        await _delete_outline(db, project_id)
    runtime.emit("stage", stage="open-book")
    runtime.emit("status", progress="开书：生成大纲细纲")
    reg = PromptRegistry()
    text = await project_text(db, project_id)
    if await runtime.factory.available("high"):
        prompt = reg.build_prompt(
            {
                "system": reg.render("system/base"),
                "project": f"【项目】{text}",
                "tracking": "【追踪】尚未开书",
                "task": "请为一本新书生成第一卷细纲。",
                "tail": f"【用户意图】{scenario or '创建大纲'}",
            }
        )
        beats = await generate_checked(
            runtime.factory, "high", prompt, OutputContract(OutlineBeats), task_type="open_book_outline"
        )
    else:
        runtime.emit("status", progress="demo 模式：使用确定性大纲")
        beats = stub_outline(scenario, text.split("\n")[0] or "新书")
    vol = Volume(project_id=project_id, no=beats.volume_no, title=beats.volume_title)
    db.add(vol)
    await db.flush()
    for c in beats.chapters:
        db.add(OutlineChapter(volume_id=vol.id, chapter_no=c.chapter_no, title=c.title, beats=c.model_dump()))
    await db.commit()
    runtime.emit("status", progress=f"大纲已生成（{len(beats.chapters)} 章）")
    return len(beats.chapters)
