"""ScanGraph（D9：US-24）：2 平台采集 → 清洗 → 质量过滤 → 趋势 → 选题 → 报告。

链路（每节点遍历 state 中的平台分支）：
  collect（榜单数据）→ clean（规整去重）→ validate（质量过滤）→ trends（分布/热词/增速）
  → decision（LLM high 选题，无 key 走确定性启发式）→ report（LLM 汇总或模板拼装）→ save（落 scan_results）

raw/cleaned/report 按平台各落一条 ScanResult 快照（append-only，前端取每平台最新）。
"""

import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.graphs.ctx import GraphRuntime
from app.graphs.stub_scan import (
    PLATFORM_NAMES,
    analyze_trends,
    clean_books,
    collect_rankings,
    generate_report,
    topic_decision,
    validate_quality,
)
from app.llm.contracts import OutputContract
from app.llm.retry import generate_checked
from app.models import ScanResult
from app.schemas.scan import ScanReportOut, TopicDecision
from app.services.prompt_registry import PromptRegistry


class ScanState(TypedDict, total=False):
    user_id: int
    task_id: int | None
    platforms: list[str]
    collected: dict[str, list]  # platform -> [raw books]
    cleaned: dict[str, dict]  # platform -> {"books": [...], "dropped": int}
    validated: dict[str, dict]  # platform -> {"books": [...], "invalid": [...]}
    trends: dict[str, dict]  # platform -> TrendReport
    decisions: dict[str, dict]  # platform -> TopicDecision
    reports: dict[str, str]  # platform -> markdown


def build_scan_graph(runtime: GraphRuntime):
    db = runtime.db
    reg = PromptRegistry()

    async def collect(state: ScanState) -> ScanState:
        runtime.check_cancel()
        runtime.emit("stage", stage="scan:collect")
        platforms = state.get("platforms") or ["qidian", "fanqie"]
        collected: dict[str, list] = {}
        for p in platforms:
            runtime.check_cancel()
            runtime.emit_tool(f"scan:collect:{p}", "running")
            books = collect_rankings(p)
            collected[p] = books
            runtime.emit_tool(f"scan:collect:{p}", "done", output=f"{len(books)} 条")
            runtime.emit("status", progress=f"{PLATFORM_NAMES.get(p, p)} 采集完成（{len(books)} 条）")
        return {"platforms": platforms, "collected": collected}

    async def clean(state: ScanState) -> ScanState:
        runtime.check_cancel()
        runtime.emit("stage", stage="scan:clean")
        cleaned: dict[str, dict] = {}
        for p, books in state["collected"].items():
            runtime.check_cancel()
            cb, dropped = clean_books(books)
            cleaned[p] = {"books": cb, "dropped": dropped}
            runtime.emit("status", progress=f"{PLATFORM_NAMES.get(p, p)} 清洗完成（丢弃 {dropped} 条）")
        return {"cleaned": cleaned}

    async def validate(state: ScanState) -> ScanState:
        runtime.check_cancel()
        runtime.emit("stage", stage="scan:validate")
        validated: dict[str, dict] = {}
        for p, v in state["cleaned"].items():
            runtime.check_cancel()
            valid, invalid = validate_quality(v["books"])
            validated[p] = {"books": valid, "invalid": invalid}
            runtime.emit("status", progress=f"{PLATFORM_NAMES.get(p, p)} 质量过滤：{len(valid)} 本有效 / {len(invalid)} 本剔除")
        return {"validated": validated}

    async def trends(state: ScanState) -> ScanState:
        runtime.check_cancel()
        runtime.emit("stage", stage="scan:trends")
        trends_map: dict[str, dict] = {}
        for p, v in state["validated"].items():
            runtime.check_cancel()
            stats = analyze_trends(v["books"])
            trends_map[p] = stats
            runtime.emit("status", progress=f"{PLATFORM_NAMES.get(p, p)} 趋势完成：{len(stats.get('hot_tags', []))} 热词")
        return {"trends": trends_map}

    async def decision(state: ScanState) -> ScanState:
        runtime.check_cancel()
        runtime.emit("stage", stage="scan:decision")
        decisions: dict[str, dict] = {}
        for p in state["trends"]:
            runtime.check_cancel()
            stats = state["trends"][p]
            books = state["validated"][p]["books"]
            if await runtime.factory.available("high"):
                payload = json.dumps({"stats": stats, "books": books[:5]}, ensure_ascii=False)
                prompt = reg.build_prompt({
                    "system": reg.render("system/base"),
                    "project": f"【扫榜选题】{PLATFORM_NAMES.get(p, p)}",
                    "tracking": f"【趋势统计】\n{json.dumps(stats, ensure_ascii=False)[:4000]}",
                    "task": "基于榜单统计给出新书选题决策。",
                    "tail": f"【头部样本】\n{payload[:6000]}",
                })
                model = await generate_checked(
                    runtime.factory, "high", prompt, OutputContract(TopicDecision), task_type="scan_topic"
                )
                decisions[p] = model.model_dump()
            else:
                decisions[p] = topic_decision(stats, books)
            runtime.emit("status", progress=f"{PLATFORM_NAMES.get(p, p)} 选题决策：{decisions[p].get('topic')}")
        return {"decisions": decisions}

    async def report(state: ScanState) -> ScanState:
        runtime.check_cancel()
        runtime.emit("stage", stage="scan:report")
        reports: dict[str, str] = {}
        for p in state["trends"]:
            runtime.check_cancel()
            stats = state["trends"][p]
            decision = state["decisions"][p]
            if await runtime.factory.available("high"):
                payload = json.dumps({"stats": stats, "decision": decision}, ensure_ascii=False)
                prompt = reg.build_prompt({
                    "system": reg.render("system/base"),
                    "project": f"【扫榜报告】{PLATFORM_NAMES.get(p, p)}",
                    "tracking": "【趋势与决策】\n" + payload[:6000],
                    "task": "生成一份结构清晰的扫榜报告（Markdown）。",
                })
                model = await generate_checked(
                    runtime.factory, "high", prompt, OutputContract(ScanReportOut), task_type="scan_report"
                )
                reports[p] = model.report
            else:
                reports[p] = generate_report(p, stats, decision)
            runtime.emit("status", progress=f"{PLATFORM_NAMES.get(p, p)} 报告生成")
        return {"reports": reports}

    async def save(state: ScanState) -> ScanState:
        runtime.check_cancel()
        runtime.emit("stage", stage="scan:save")
        for p in state["platforms"]:
            v = state["validated"][p]
            db.add(
                ScanResult(
                    owner_id=state["user_id"],
                    platform=p,
                    raw={"platform": p, "books": state["collected"][p]},
                    cleaned={
                        "platform": p,
                        "books": v["books"],
                        "invalid": v["invalid"],
                        "dropped": state["cleaned"][p]["dropped"],
                        "stats": state["trends"][p],
                        "topic_decision": state["decisions"][p],
                    },
                    report=state["reports"][p],
                )
            )
        await db.commit()
        runtime.emit(
            "checkpoint",
            platforms=state["platforms"],
            topic_decision={p: state["decisions"][p].get("topic") for p in state["platforms"]},
        )
        runtime.emit("status", progress="扫榜完成，结果已落库")
        return {}

    graph = StateGraph(ScanState)
    graph.add_node("collect", collect)
    graph.add_node("clean", clean)
    graph.add_node("validate", validate)
    graph.add_node("trends", trends)
    graph.add_node("decision", decision)
    graph.add_node("report", report)
    graph.add_node("save", save)
    graph.add_edge(START, "collect")
    graph.add_edge("collect", "clean")
    graph.add_edge("clean", "validate")
    graph.add_edge("validate", "trends")
    graph.add_edge("trends", "decision")
    graph.add_edge("decision", "report")
    graph.add_edge("report", "save")
    graph.add_edge("save", END)
    return graph.compile()
