"""开书流水线服务（D13+）：世界观 → 大纲 → 细纲 三阶段生成/提交 + 按阶段重试。

每阶段产出一份「草稿文本」（markdown 约定格式），流式 emit token（stream=阶段名）。
- auto 模式：生成完直接解析落库（generate_outline，写图 ensure_outline 与 open_book 自动模式共用）。
- confirm 模式：任务执行器收到草稿后暂停，等用户确认/修改/重新生成再提交（draft_stage/commit_stage 接口）。

重试语义：stage=X 时清掉 X 及其后的产物，从 X 起跑；X 之前的产物保留。
"""

import asyncio
import re

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graphs.ctx import GraphRuntime
from app.graphs.stub import stub_chapter_beats, stub_outline_structure, stub_worldview
from app.models import OutlineChapter, Project, Setting, Volume
from app.schemas.writing import BeatsDetail, ChapterBeats, OutlineStructure, OutlineStructureChapter, SettingItem, WorldviewBeats
from app.services.prompt_registry import PromptRegistry

STAGE_ORDER = ["worldview", "outline", "beats"]
STAGE_LABELS = {"worldview": "世界观/设定", "outline": "大纲", "beats": "细纲"}

CHUNK = 4
CHUNK_DELAY = 0.005


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
    """归一化两种已存在形状：开书写入 {summary, target_wordcount, points} 与
    拆文导入 {summary, beats:[...]} → 统一输出 {summary, target_wordcount, points}。"""
    if not beats:
        return {"summary": "", "target_wordcount": None, "points": []}
    points = beats["beats"] if isinstance(beats.get("beats"), list) else beats.get("points") or []
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


# ---- 草稿文本解析（markdown 约定格式 → 结构化） ----

def _parse_worldview(text: str) -> WorldviewBeats:
    items: list[SettingItem] = []
    current = "世界观"
    buf: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^\s*#+\s*(.+?)\s*$", line)
        if m:
            body = "\n".join(buf).strip()
            if body:
                items.append(SettingItem(kind=current[:32], title="", content=body))
            current = m.group(1).strip() or "世界观"
            buf = []
        else:
            buf.append(line)
    body = "\n".join(buf).strip()
    if body:
        items.append(SettingItem(kind=current[:32], title="", content=body))
    if not items:
        items.append(SettingItem(kind="世界观", title="", content=text.strip()))
    return WorldviewBeats(settings=items)


def _parse_outline(text: str) -> OutlineStructure:
    vol_title = "第一卷"
    chapters: list[OutlineStructureChapter] = []
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^卷名\s*[：:]\s*(.+)$", s)
        if m:
            vol_title = m.group(1).strip()[:128] or vol_title
            continue
        m = re.match(r"^第\s*(\d+)\s*章\s*(.*)$", s)
        if m:
            no = int(m.group(1))
            chapters.append(OutlineStructureChapter(chapter_no=no, title=(m.group(2).strip() or f"第{no}章")[:64]))
    if not chapters:
        chapters = [OutlineStructureChapter(chapter_no=i + 1, title=f"第{i + 1}章") for i in range(3)]
    return OutlineStructure(volume_no=1, volume_title=vol_title, chapters=chapters)


def _parse_beats(text: str) -> BeatsDetail:
    chapters: list[ChapterBeats] = []
    cur: ChapterBeats | None = None
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^第\s*(\d+)\s*章\s*(.*)$", s)
        if m:
            if cur is not None and (cur.summary or cur.points):
                chapters.append(cur)
            cur = ChapterBeats(chapter_no=int(m.group(1)), title=m.group(2).strip())
            continue
        if cur is None:
            continue
        m = re.match(r"^摘要\s*[：:]\s*(.+)$", s)
        if m:
            cur.summary = m.group(1).strip()
            continue
        m = re.match(r"^[-*]\s*(.+)$", s)
        if m:
            cur.points.append(m.group(1).strip())
    if cur is not None and (cur.summary or cur.points):
        chapters.append(cur)
    if not chapters:
        chapters = [ChapterBeats(chapter_no=1, summary=text.strip()[:200])]
    return BeatsDetail(chapters=chapters)


# ---- 各阶段草稿生成（流式 emit token） ----

async def _stream_stub(runtime: GraphRuntime, text: str, stream: str) -> str:
    for i in range(0, len(text), CHUNK):
        runtime.check_cancel()
        runtime.emit("token", content=text[i : i + CHUNK], stream=stream)
        await asyncio.sleep(CHUNK_DELAY)
    return text


async def _stream_llm(runtime: GraphRuntime, prompt: str, tier: str, task_type: str, stream: str) -> str:
    parts: list[str] = []
    async for chunk in runtime.factory.stream(tier, [("human", prompt)], task_type=task_type):
        runtime.check_cancel()
        parts.append(chunk)
        runtime.emit("token", content=chunk, stream=stream)
        await asyncio.sleep(0)
    return "".join(parts)


async def _draft_worldview(db: AsyncSession, runtime: GraphRuntime, project_id: int, scenario: str) -> str:
    runtime.emit("stage", stage="worldview")
    runtime.emit("status", progress="开书：生成世界观/设定")
    reg = PromptRegistry()
    text = await project_text(db, project_id)
    stub = stub_worldview(scenario, text.split("\n")[0] or "新书")
    if await runtime.factory.available("high"):
        prompt = reg.build_prompt(
            {
                "system": reg.render("system/base"),
                "project": f"【项目】{text}",
                "tracking": "【追踪】开书：世界观设定",
                "task": "请生成这本小说的世界观/设定草稿。必须用 markdown 段落格式，每个段落以「## 段落名」开头，示例：\n## 世界观\n……\n## 人设\n……\n## 金手指\n……",
                "tail": f"【用户意图】{scenario or '创建世界观'}",
            }
        )
        draft = (await _stream_llm(runtime, prompt, "high", "open_book_worldview", "worldview")).strip()
        if not draft or not _parse_worldview(draft).settings:
            draft = stub
    else:
        runtime.emit("status", progress="demo 模式：生成确定性世界观/设定")
        draft = await _stream_stub(runtime, stub, "worldview")
    runtime.emit("status", progress="世界观草稿已生成")
    return draft


async def _draft_outline(db: AsyncSession, runtime: GraphRuntime, project_id: int, scenario: str) -> str:
    runtime.emit("stage", stage="outline")
    runtime.emit("status", progress="开书：生成卷/章大纲")
    reg = PromptRegistry()
    text = await project_text(db, project_id)
    stub = stub_outline_structure(scenario, text.split("\n")[0] or "新书")
    if await runtime.factory.available("high"):
        prompt = reg.build_prompt(
            {
                "system": reg.render("system/base"),
                "project": f"【项目】{text}",
                "tracking": "【追踪】开书：大纲结构",
                "task": "请生成第一卷大纲草稿。必须用如下格式：\n卷名：<卷名>\n第1章 <标题>\n第2章 <标题>\n……",
                "tail": f"【用户意图】{scenario or '创建大纲'}",
            }
        )
        draft = (await _stream_llm(runtime, prompt, "high", "open_book_outline", "outline")).strip()
        if not draft or not _parse_outline(draft).chapters:
            draft = stub
    else:
        runtime.emit("status", progress="demo 模式：生成确定性卷/章大纲")
        draft = await _stream_stub(runtime, stub, "outline")
    runtime.emit("status", progress="大纲草稿已生成")
    return draft


async def _draft_beats(db: AsyncSession, runtime: GraphRuntime, project_id: int, scenario: str) -> str:
    runtime.emit("stage", stage="beats")
    runtime.emit("status", progress="开书：生成各章细纲")
    reg = PromptRegistry()
    text = await project_text(db, project_id)
    stub = stub_chapter_beats()
    if await runtime.factory.available("high"):
        prompt = reg.build_prompt(
            {
                "system": reg.render("system/base"),
                "project": f"【项目】{text}",
                "tracking": "【追踪】开书：章节细纲",
                "task": "请为第一卷各章生成细纲草稿。每章必须用如下格式：\n第N章 <标题>\n摘要：<一句话>（指本章主旨）\n情节点：\n- <情节点1>\n- <情节点2>",
                "tail": f"【用户意图】{scenario or '创建细纲'}",
            }
        )
        draft = (await _stream_llm(runtime, prompt, "high", "open_book_beats", "beats")).strip()
        if not draft or not _parse_beats(draft).chapters:
            draft = stub
    else:
        runtime.emit("status", progress="demo 模式：生成确定性细纲")
        draft = await _stream_stub(runtime, stub, "beats")
    runtime.emit("status", progress="细纲草稿已生成")
    return draft


# ---- 各阶段提交（解析草稿 → 落库） ----

async def _delete_outline(db: AsyncSession, project_id: int) -> None:
    vids = list((await db.scalars(select(Volume.id).where(Volume.project_id == project_id))).all())
    if vids:
        await db.execute(delete(OutlineChapter).where(OutlineChapter.volume_id.in_(vids)))
    await db.execute(delete(Volume).where(Volume.project_id == project_id))
    await db.flush()


async def _commit_worldview(db: AsyncSession, project_id: int, text: str) -> int:
    parsed = _parse_worldview(text)
    # v1：开书是项目设定的唯一生成来源，提交即整体替换
    await db.execute(delete(Setting).where(Setting.project_id == project_id))
    for it in parsed.settings:
        db.add(Setting(project_id=project_id, kind=it.kind, title=it.title, content=it.content))
    await db.commit()
    return len(parsed.settings)


async def _commit_outline(db: AsyncSession, project_id: int, text: str) -> int:
    parsed = _parse_outline(text)
    await _delete_outline(db, project_id)
    vol = Volume(project_id=project_id, no=parsed.volume_no, title=parsed.volume_title, synopsis=parsed.synopsis)
    db.add(vol)
    await db.flush()
    for ch in parsed.chapters:
        db.add(OutlineChapter(volume_id=vol.id, chapter_no=ch.chapter_no, title=ch.title, beats={}))
    await db.commit()
    return len(parsed.chapters)


async def _commit_beats(db: AsyncSession, project_id: int, text: str) -> int:
    parsed = _parse_beats(text)
    vols = (await db.scalars(select(Volume).where(Volume.project_id == project_id).order_by(Volume.no))).all()
    if not vols:
        # 细纲依赖卷：卷缺失（如中途被清）时用 stub 结构兜底补齐
        await _commit_outline(db, project_id, stub_outline_structure("", ""))
        vols = (await db.scalars(select(Volume).where(Volume.project_id == project_id).order_by(Volume.no))).all()
    vid = vols[0].id
    rows = (await db.scalars(select(OutlineChapter).where(OutlineChapter.volume_id == vid))).all()
    by_no = {r.chapter_no: r for r in rows}
    for cb in parsed.chapters:
        row = by_no.get(cb.chapter_no)
        if row is None:
            row = OutlineChapter(
                volume_id=vid, chapter_no=cb.chapter_no, title=cb.title or f"第{cb.chapter_no}章", beats={}
            )
            db.add(row)
            by_no[cb.chapter_no] = row
        if cb.title:
            row.title = cb.title
        row.beats = {"summary": cb.summary, "target_wordcount": cb.target_wordcount, "points": cb.points}
    await db.commit()
    return len(parsed.chapters)


# ---- 重试清理 ----

async def clear_from(db: AsyncSession, project_id: int, stage: str) -> None:
    """清除 stage 及其后的所有产物（重试语义）；stage 之前保留。"""
    idx = STAGE_ORDER.index(stage)
    if idx <= 0:  # worldview 起跑 → 全清（含设定）
        await db.execute(delete(Setting).where(Setting.project_id == project_id))
    if idx <= 1:  # outline 起跑 → 清卷+章
        await _delete_outline(db, project_id)
    # beats 起跑 → 无需预清，_commit_beats 原位覆盖 beats
    await db.flush()


# ---- 对外接口 ----

DRAFT_GENERATORS = {"worldview": _draft_worldview, "outline": _draft_outline, "beats": _draft_beats}
STAGE_COMMITTERS = {"worldview": _commit_worldview, "outline": _commit_outline, "beats": _commit_beats}


async def draft_stage(db: AsyncSession, runtime: GraphRuntime, stage: str, project_id: int, scenario: str) -> str:
    return await DRAFT_GENERATORS[stage](db, runtime, project_id, scenario)


async def commit_stage(db: AsyncSession, runtime: GraphRuntime, stage: str, project_id: int, text: str) -> int:
    del runtime  # 提交不需要运行时（兼容调用方统一签名）
    return await STAGE_COMMITTERS[stage](db, project_id, text)


async def generate_outline(
    db: AsyncSession,
    runtime: GraphRuntime,
    *,
    project_id: int,
    scenario: str = "",
    force: bool = False,
    stage: str = "all",
) -> int:
    """开书 auto 流水线：从指定阶段起跑，各阶段生成即提交。

    - stage="all"：已有大纲且非 force → 静默跳过（返回现有章数）；force → 全清重跑。
    - stage=X（worldview/outline/beats）：重试语义，清 X 及其后产物，从 X 起跑。
    """
    if stage == "all":
        if await outline_count(db, project_id) > 0 and not force:
            return await outline_count(db, project_id)
        start = STAGE_ORDER[0]
        if force:
            await clear_from(db, project_id, "worldview")
    else:
        if stage not in STAGE_ORDER:
            raise ValueError(f"未知开书阶段: {stage}")
        start = stage
        await clear_from(db, project_id, stage)

    for s in STAGE_ORDER[STAGE_ORDER.index(start):]:
        draft = await DRAFT_GENERATORS[s](db, runtime, project_id, scenario)
        await STAGE_COMMITTERS[s](db, project_id, draft)
    return await outline_count(db, project_id)
