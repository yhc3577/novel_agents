"""ReviewGraph（D8：US-21）：full/lean/solo 审查 + 4 reviewer `Send` 并行 + 汇总。

链路：load（取正文+大纲上下文）→ reviewer×4（map：plot/character/style/rhythm，
reducer 合并 findings）→ summarize（打分/结论，落 chapter_reviews）。
LLM 无 key 时 4 个 reviewer 跑确定性启发式扫描（stub_review）。
"""

from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from sqlalchemy import select

from app.graphs.ctx import GraphRuntime
from app.graphs.stub_review import REVIEWERS, stub_review, stub_summary
from app.llm.contracts import OutputContract
from app.llm.retry import generate_checked
from app.models import Chapter, ChapterReview, OutlineChapter, Volume
from app.schemas.review import ReviewFinding, ReviewSummary, ReviewerOutput
from app.services.prompt_registry import PromptRegistry


def _merge_findings(a: list | None, b: list | None) -> list:
    return (a or []) + (b or [])


class ReviewState(TypedDict, total=False):
    user_id: int
    project_id: int
    chapter_no: int
    task_id: int | None
    mode: str  # full/lean/solo
    chapter_text: str
    context: str
    findings: Annotated[list, _merge_findings]
    score: int
    verdict: str
    summary_text: str


def build_review_graph(runtime: GraphRuntime):
    db = runtime.db
    reg = PromptRegistry()

    async def load(state: ReviewState) -> ReviewState:
        runtime.check_cancel()
        runtime.emit("stage", stage="review:load")
        pid, no = state["project_id"], state["chapter_no"]
        ch = await db.scalar(
            select(Chapter).where(Chapter.project_id == pid, Chapter.chapter_no == no, Chapter.status == "committed")
        )
        if ch is None:
            raise ValueError(f"第 {no} 章尚未提交，无法审查")
        # 大纲上下文（细纲情节点）
        vols = await db.scalars(select(Volume).where(Volume.project_id == pid))
        oc = await db.scalar(
            select(OutlineChapter).where(OutlineChapter.volume_id.in_([v.id for v in vols]), OutlineChapter.chapter_no == no)
        )
        beats = (oc.beats or {}).get("summary", "") if oc and oc.beats else ""
        runtime.emit("status", progress=f"第 {no} 章审查：读取正文（{ch.wordcount} 字）")
        return {"chapter_text": ch.content or "", "context": beats}

    async def reviewer(state: ReviewState) -> ReviewState:
        runtime.check_cancel()
        who = state["reviewer"]  # 由 Send payload 注入
        label = state["reviewer_label"]
        runtime.emit("tool", tool=f"reviewer:{who}", status="running")
        if await runtime.factory.available("mid"):
            prompt = reg.build_prompt({
                "system": reg.render("system/base"),
                "project": f"【审查】{label} 维度（project {state['project_id']}）",
                "tracking": f"【大纲细纲】{state.get('context') or '无'}",
                "task": f"请从「{label}」维度审查本章，逐条给出问题。",
                "tail": f"【章节正文】\n{(state.get('chapter_text') or '')[:6000]}",
            })
            model = await generate_checked(
                runtime.factory, "mid", prompt, OutputContract(ReviewerOutput), task_type="review"
            )
            findings = [f.model_dump() | {"reviewer": who} for f in model.findings]
        else:
            findings = stub_review(who, state.get("chapter_text", ""), state.get("context", ""))
        runtime.emit("tool", tool=f"reviewer:{who}", status="done")
        runtime.emit("status", progress=f"{label}审查完成（{len(findings)} 条）")
        return {"findings": findings}

    async def summarize(state: ReviewState) -> ReviewState:
        runtime.check_cancel()
        runtime.emit("stage", stage="review:summarize")
        findings = state.get("findings", [])
        if await runtime.factory.available("high"):
            payload = "\n".join(
                f"- [{f['severity']}][{f['reviewer']}] {f['reason']}「{f['quote'][:50]}」建议:{f['suggestion']}" for f in findings
            ) or "（无问题）"
            prompt = reg.build_prompt({
                "system": reg.render("system/base"),
                "project": f"【审查汇总】project {state['project_id']} 第 {state['chapter_no']} 章",
                "tracking": "【模式】" + state.get("mode", "full"),
                "task": "基于各 reviewer findings 生成总体结论。",
                "tail": f"【findings】\n{payload[:8000]}",
            })
            model = await generate_checked(runtime.factory, "high", prompt, OutputContract(ReviewSummary), task_type="review_summary")
            score, verdict, must_fix, advice = model.score, model.verdict, model.must_fix, model.advice
        else:
            score, verdict, must_fix, advice = stub_summary(findings)
        summary_text = advice + ("\n必改：\n- " + "\n- ".join(must_fix) if must_fix else "")
        # 落库
        row = await db.scalar(
            select(ChapterReview).where(
                ChapterReview.project_id == state["project_id"],
                ChapterReview.chapter_no == state["chapter_no"],
                ChapterReview.mode == state.get("mode", "full"),
            )
        )
        if row is None:
            db.add(
                ChapterReview(
                    project_id=state["project_id"], chapter_no=state["chapter_no"], mode=state.get("mode", "full"),
                    score=score, verdict=verdict, findings=findings, summary=summary_text,
                )
            )
        else:
            row.score, row.verdict, row.findings, row.summary = score, verdict, findings, summary_text
        await db.commit()
        runtime.emit("checkpoint", chapter_no=state["chapter_no"], score=score, verdict=verdict, findings=len(findings))
        runtime.emit("status", progress=f"审查完成：{score} 分 / {verdict}（{len(findings)} 条）")
        return {"score": score, "verdict": verdict, "summary_text": summary_text}

    def route_review(state: ReviewState):
        return [
            Send("reviewer", {"reviewer": key, "reviewer_label": label, "chapter_text": state.get("chapter_text", ""), "context": state.get("context", "")})
            for key, label in REVIEWERS
        ]

    graph = StateGraph(ReviewState)
    graph.add_node("load", load)
    graph.add_node("reviewer", reviewer)
    graph.add_node("summarize", summarize)
    graph.add_edge(START, "load")
    graph.add_conditional_edges("load", route_review, ["reviewer"])
    graph.add_edge("reviewer", "summarize")
    graph.add_edge("summarize", END)
    return graph.compile()
