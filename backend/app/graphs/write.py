"""WriteGraph（US-13）：开书三阶段 + 写一章 + 日更循环（最小版）。

链路：prepare → ensure_outline → plan → write_chapter → submit →（日更? 回写章 : END）。
节点通过 GraphRuntime 访问 DB 会话、SSE emit、取消信号；LLM 无 key 时走确定性兜底。

prompt 装配遵循 §5.2：段 1-4（system/project/tracking/task）任务内稳定，段 5 可变尾部。
"""

import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.graphs.ctx import GraphRuntime
from app.graphs.stub import stub_content, stub_tracking
from app.llm.contracts import OutputContract
from app.llm.retry import generate_checked
from app.models import Chapter, OutlineChapter, Project, Setting, TrackingState, Volume
from app.schemas.tracking import TrackingTx
from app.schemas.writing import WritePlan
from app.services.chapter import ChapterService
from app.services.outline import generate_outline
from app.services.context import ContextService
from app.services.prompt_registry import PromptRegistry
from app.services.tracking import TrackingService

# 日更循环单次任务上限（MVP 防失控）
DAILY_CAP = 3
# demo 流式分块大小/间隔
CHUNK = 4
CHUNK_DELAY = 0.005


class WriteState(TypedDict, total=False):
    user_id: int
    project_id: int
    task_id: int | None
    action: str  # write_next / write_chapter / daily
    scenario: str
    chapter_no: int | None
    target: int | None
    max_chapter: int
    iterations: int
    project_text: str
    context_view: str
    recall_pack: dict
    previous_content: str
    content: str | None
    tracking: dict | None
    draft_id: int | None
    error: str | None
    more: bool


def build_write_graph(runtime: GraphRuntime):
    """基于给定运行时构建并编译 WriteGraph。"""
    db = runtime.db
    reg = PromptRegistry()

    # ---- 内部辅助（先定义，节点闭包引用） ----

    async def _project_text(project_id: int) -> str:
        project = await db.get(Project, project_id)
        rows = await db.scalars(select(Setting).where(Setting.project_id == project_id))
        settings = "；".join(f"{s.kind}/{s.title}：{s.content}" for s in rows if s.content)
        return f"{project.title}（{project.genre or ''}/{project.platform or ''}）\n{settings}"

    async def _outline_count(project_id: int) -> int:
        vols = await db.scalars(select(Volume).where(Volume.project_id == project_id))
        if not vols:
            return 0
        rows = await db.scalars(
            select(OutlineChapter)
            .where(OutlineChapter.volume_id.in_([v.id for v in vols]))
            .order_by(OutlineChapter.chapter_no.desc())
            .limit(1)
        )
        last = rows.first()
        return last.chapter_no if last else 0

    async def _outline_for(project_id: int, chapter_no: int) -> OutlineChapter | None:
        vols = await db.scalars(select(Volume).where(Volume.project_id == project_id))
        vid = [v.id for v in vols]
        if not vid:
            return None
        return await db.scalar(
            select(OutlineChapter).where(OutlineChapter.volume_id.in_(vid), OutlineChapter.chapter_no == chapter_no)
        )

    async def _chapter_title(project_id: int, chapter_no: int) -> str:
        oc = await _outline_for(project_id, chapter_no)
        if oc:
            return oc.title
        return f"第{chapter_no}章"

    async def _preview_gate(chapter_id: int) -> None:
        from app.services.quality import QualityService

        await QualityService(db).full_gate(chapter_id, fail_on="none")

    async def _stream_llm(runtime: GraphRuntime, prompt: str, target: int) -> str:
        parts: list[str] = []
        async for chunk in runtime.factory.stream("mid", [("human", prompt)], task_type="narrative_writer"):
            runtime.check_cancel()
            parts.append(chunk)
            runtime.emit("token", content=chunk)
            await asyncio.sleep(0)
        text = "".join(parts)
        # 字数收口兜底：LLM 产出不足时补齐（保持可运行）
        if len(text) < target:
            text += "\n\n" + stub_content(0, "", "")[: target - len(text)]
        return text

    async def _stub_stream(runtime: GraphRuntime, text: str) -> str:
        for i in range(0, len(text), CHUNK):
            runtime.check_cancel()
            runtime.emit("token", content=text[i : i + CHUNK])
            await asyncio.sleep(CHUNK_DELAY)
        return text

    # ---- 节点 ----

    async def prepare(state: WriteState) -> WriteState:
        runtime.emit("stage", stage="prepare")
        pid = state["project_id"]
        # 开书：尚无追踪状态则初始化（revision 从 1 起）
        state_row = await db.scalar(select(TrackingState).where(TrackingState.project_id == pid))
        if state_row is None:
            await TrackingService(db).init(pid, {"seed": "开书初始化"})
            await db.commit()
        info = await runtime.run_tool("TrackingService.check", lambda: TrackingService(db).check(pid))
        max_chapter = await _outline_count(pid)
        chapter_no = state.get("chapter_no") or info["last_committed_chapter"] + 1
        if state.get("target") is None:
            target = await ChapterService(db).target_wordcount(pid, chapter_no)
        else:
            target = state["target"]
        pack = await ContextService(db).recall_pack(pid)
        prev = ""
        if chapter_no > 1:
            last = await db.scalar(
                select(Chapter)
                .where(Chapter.project_id == pid, Chapter.chapter_no == chapter_no - 1, Chapter.status == "committed")
            )
            if last:
                prev = (last.content or "")[-200:]
        runtime.emit("status", progress=f"准备第 {chapter_no} 章", last_committed_chapter=info["last_committed_chapter"])
        return {
            "chapter_no": chapter_no,
            "target": target,
            "max_chapter": max_chapter,
            "project_text": await _project_text(pid),
            "context_view": pack["context_view"],
            "recall_pack": pack,
            "previous_content": prev,
            "iterations": state.get("iterations", 0),
        }

    async def ensure_outline(state: WriteState) -> WriteState:
        """无细纲时自动开书；已有则静默跳过（生成逻辑收敛在 app.services.outline）。"""
        pid = state["project_id"]
        await generate_outline(db, runtime, project_id=pid, scenario=state.get("scenario", ""))
        return {"max_chapter": await _outline_count(pid)}

    async def plan(state: WriteState) -> WriteState:
        runtime.emit("stage", stage="planning")
        if await runtime.factory.available("low"):
            prompt = reg.build_prompt({
                "system": reg.render("system/base"),
                "project": f"【项目】{state['project_text']}",
                "tracking": f"【追踪】{state['context_view']}",
                "task": "请制定本章写作方案。",
                "tail": f"【本章】第 {state['chapter_no']} 章",
            })
            plan = await generate_checked(runtime.factory, "low", prompt, OutputContract(WritePlan), task_type="write_plan")
            target = plan.target_length
        else:
            target = state.get("target") or 2000
        runtime.emit("status", progress=f"第 {state['chapter_no']} 章目标 {target} 字")
        return {"target": target}

    async def write_chapter(state: WriteState) -> WriteState:
        runtime.check_cancel()
        runtime.emit("stage", stage="writing")
        pid = state["project_id"]
        chapter_no = state["chapter_no"]
        title = await _chapter_title(pid, chapter_no)

        segments = {
            "system": reg.render("system/base"),
            "project": f"【项目设定】{state['project_text']}",
            "tracking": f"【追踪上下文】{state['context_view']}\n【召回包】{state['recall_pack']}",
            "task": f"【任务】创作第 {chapter_no} 章「{title}」，目标 {state['target']} 字，只输出正文。",
            "tail": f"【上一章结尾】{state['previous_content']}",
        }
        prompt = reg.build_prompt(segments)

        if await runtime.factory.available("mid"):
            content = await _stream_llm(runtime, prompt, state["target"])
        else:
            runtime.emit("status", progress="demo 模式：流式生成正文")
            oc = await _outline_for(pid, chapter_no)
            summary = (oc.beats or {}).get("summary", "") if oc and oc.beats else ""
            content = await _stub_stream(runtime, stub_content(chapter_no, title, summary, state["target"]))

        # 追踪提取（结构化契约）
        if await runtime.factory.available("low"):
            tx_prompt = reg.build_prompt({
                "system": reg.render("system/base"),
                "project": "【追踪提取】",
                "tracking": f"【追踪上下文】{state['context_view']}",
                "task": "根据本章正文提取追踪事务。",
                "tail": f"【本章正文】\n{content[-3000:]}",
            })
            tracking_model = await generate_checked(
                runtime.factory, "low", tx_prompt, OutputContract(TrackingTx), task_type="tracking_extract"
            )
        else:
            tracking_model = stub_tracking(chapter_no)

        ch = await ChapterService(db).draft(pid, chapter_no, content, title=title)
        await runtime.run_tool("QualityService.full_gate", lambda: _preview_gate(ch.id))
        runtime.emit("status", progress=f"第 {chapter_no} 章草稿完成（{ch.wordcount} 字）")
        return {
            "content": content,
            "tracking": tracking_model.model_dump(),
            "draft_id": ch.id,
            "iterations": state["iterations"] + 1,
        }

    async def submit(state: WriteState) -> WriteState:
        runtime.check_cancel()
        runtime.emit("stage", stage="submitting")
        pid = state["project_id"]
        chapter_no = state["chapter_no"]
        await ChapterService(db).commit(pid, chapter_no, state["tracking"], fail_on="blocking")
        info = await TrackingService(db).check(pid)
        runtime.emit("checkpoint", **info)
        runtime.emit("status", progress=f"第 {chapter_no} 章已提交（revision={info['state_revision']}）")
        more = (
            state.get("action") == "daily"
            and chapter_no < state.get("max_chapter", 0)
            and state["iterations"] < DAILY_CAP
        )
        return {"more": more}

    async def decide(state: WriteState) -> WriteState:
        runtime.check_cancel()
        if state.get("more"):
            runtime.emit("status", progress=f"日更循环：继续第 {state['chapter_no'] + 1} 章")
            return {"chapter_no": state["chapter_no"] + 1}
        return {}

    # ---- 装配 ----

    graph = StateGraph(WriteState)
    graph.add_node("prepare", prepare)
    graph.add_node("ensure_outline", ensure_outline)
    graph.add_node("plan", plan)
    graph.add_node("write_chapter", write_chapter)
    graph.add_node("submit", submit)
    graph.add_node("decide", decide)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "ensure_outline")
    graph.add_edge("ensure_outline", "plan")
    graph.add_edge("plan", "write_chapter")
    graph.add_edge("write_chapter", "submit")
    graph.add_edge("submit", "decide")
    graph.add_conditional_edges(
        "decide",
        lambda s: "write_chapter" if s.get("more") else END,
        {"write_chapter": "write_chapter", END: END},
    )
    return graph.compile()
