"""DeslopGraph（D8：US-22）：去味——AI 扫描 → 定级（Gate A-G）→ 改写。

改写正文 original/rewritten 存入 deslop_runs（chapters 表 project_id+chapter_no 唯一，
无法同时保留 committed 与 draft 两行，故不写 chapters）；前端做前后对比；
用户确认后通过 accept API 把 rewritten 写回 committed 行。
LLM 无 key 时走 stub_deslop（短语替换 + 标点压缩）。
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.graphs.ctx import GraphRuntime
from app.graphs.stub_review import grade_findings, stub_deslop
from app.llm.contracts import OutputContract
from app.llm.retry import generate_checked
from app.models import Chapter, DeslopRun
from app.schemas.review import DeslopOut
from app.services.prompt_registry import PromptRegistry
from app.services.quality import QualityService
from app.services.wordcount import measure_text


class DeslopState(TypedDict, total=False):
    user_id: int
    project_id: int
    chapter_no: int
    task_id: int | None
    original: str
    findings: list
    grade: str
    score: int
    grade_desc: str
    rewritten: str


def build_deslop_graph(runtime: GraphRuntime):
    db = runtime.db
    reg = PromptRegistry()

    async def scan(state: DeslopState) -> DeslopState:
        runtime.check_cancel()
        runtime.emit("stage", stage="deslop:scan")
        pid, no = state["project_id"], state["chapter_no"]
        ch = await db.scalar(
            select(Chapter).where(Chapter.project_id == pid, Chapter.chapter_no == no, Chapter.status == "committed")
        )
        if ch is None:
            raise ValueError(f"第 {no} 章尚未提交，无法去味")
        report = await QualityService(db).full_gate(ch.id, fail_on="none")
        findings = [
            {"severity": f.level, "type": f.type, "quote": f.quote, "reason": f.reason, "suggestion": "删除或改写"}
            for f in report.findings
        ]
        runtime.emit("status", progress=f"扫描完成（{len(findings)} 处问题）")
        return {"original": ch.content or "", "findings": findings}

    async def grade(state: DeslopState) -> DeslopState:
        runtime.check_cancel()
        runtime.emit("stage", stage="deslop:grade")
        grade, score, desc = grade_findings(state["findings"])
        runtime.emit("status", progress=f"定级：Gate {grade}（{score} 分）{desc}")
        return {"grade": grade, "score": score, "grade_desc": desc}

    async def rewrite(state: DeslopState) -> DeslopState:
        runtime.check_cancel()
        runtime.emit("stage", stage="deslop:rewrite")
        pid, no = state["project_id"], state["chapter_no"]
        if await runtime.factory.available("mid"):
            payload = "\n".join(f"- [{f['severity']}] {f['reason']}「{f['quote'][:40]}」" for f in state["findings"]) or "（无问题）"
            prompt = reg.build_prompt({
                "system": reg.render("system/base"),
                "project": f"【去味】project {pid} 第 {no} 章",
                "tracking": "【扫描问题】\n" + payload,
                "task": "改写本章，逐条消除上述 AI 味/退化/标点问题，保持情节与人设不变，只输出改写后的正文。",
                "tail": f"【原正文】\n{(state.get('original') or '')[:8000]}",
            })
            model = await generate_checked(runtime.factory, "mid", prompt, OutputContract(DeslopOut), task_type="deslop")
            rewritten = model.rewritten
        else:
            rewritten = stub_deslop(state.get("original", ""))
        # 落 DeslopRun（original/rewritten 都在此表，不动 chapters 唯一行）
        original = state.get("original", "")
        run = await db.scalar(select(DeslopRun).where(DeslopRun.project_id == pid, DeslopRun.chapter_no == no))
        if run is None:
            db.add(
                DeslopRun(
                    project_id=pid, chapter_no=no, grade=state["grade"], score=state["score"],
                    findings=state["findings"], original=original, rewritten=rewritten,
                )
            )
        else:
            run.grade, run.score, run.findings = state["grade"], state["score"], state["findings"]
            run.original, run.rewritten = original, rewritten
        await db.commit()
        runtime.emit("checkpoint", chapter_no=no, grade=state["grade"], score=state["score"], wordcount=measure_text(rewritten))
        runtime.emit("status", progress=f"去味完成：Gate {state['grade']}，改写 {measure_text(rewritten)} 字（原 {measure_text(original)} 字）")
        return {"rewritten": rewritten}

    graph = StateGraph(DeslopState)
    graph.add_node("scan", scan)
    graph.add_node("grade", grade)
    graph.add_node("rewrite", rewrite)
    graph.add_edge(START, "scan")
    graph.add_edge("scan", "grade")
    graph.add_edge("grade", "rewrite")
    graph.add_edge("rewrite", END)
    return graph.compile()
