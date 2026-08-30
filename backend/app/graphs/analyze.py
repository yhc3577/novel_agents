"""AnalyzeGraph（D6：US-18）：上传文本 → 章节拆解 → 多维聚合 → 报告。

链路（stage0-6，全程落 analysis_progress 断点，重跑从失败/pending 处续）：
  stage0 boundaries: 正则切「第X章」边界，幂等补齐 analysis_chapters
  stage1 extract:    map 并行（asyncio.gather）逐章 chapter-extractor（契约 ChapterExtraction）
  stage2-5 aggregate: 各阶段落 1-2 个 kind 的 analysis_aggregates（plot/rhythm/emotion/
                     characters/settings/relations/style/golden）
  stage6 report:     总报告 + 书 status→done

LLM 无 key 时走 stub_analysis 的确定性文本统计（真实计算，非占位）。
"""

import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.graphs.ctx import GraphRuntime
from app.graphs.stub_analysis import AGGREGATORS, aggregate_report, extract_chapter, split_chapters
from app.llm.contracts import OutputContract
from app.llm.retry import generate_checked
from app.models import AnalysisAggregate, AnalysisBook
from app.schemas.analysis import AnalysisOut, ChapterExtraction
from app.services.analysis import STAGE_KINDS, AnalysisService
from app.services.prompt_registry import PromptRegistry

MAX_BATCH_PARALLEL = 8  # map 并行上限（防止一次性打开过多并发调用）


class AnalyzeState(TypedDict, total=False):
    user_id: int
    book_id: int
    task_id: int | None
    stage: str


def build_analyze_graph(runtime: GraphRuntime, book_id: int):
    db = runtime.db
    svc = AnalysisService(db)
    reg = PromptRegistry()

    async def _book() -> AnalysisBook:
        book = await db.get(AnalysisBook, book_id)
        if book is None:
            raise ValueError(f"拆文书不存在: {book_id}")
        return book

    async def _chapter_texts() -> tuple[list[str], list[str]]:
        """重算章节边界并返回 [text...]、[title...]（stage0 确定性，断点可复现）。"""
        book = await _book()
        bounds = split_chapters(book.source_text or "")
        texts = [book.source_text[b["start"] : b["end"]] for b in bounds]
        titles = [b["title"] for b in bounds]
        return texts, titles

    # ---- stage0：切章 ----

    async def boundaries(state: AnalyzeState) -> AnalyzeState:
        runtime.check_cancel()
        runtime.emit("stage", stage="split")
        book = await _book()
        bounds = split_chapters(book.source_text or "")
        await svc.ensure_chapters(book_id, bounds)
        await svc.mark_stage(book_id, "stage0")
        await db.commit()
        runtime.emit("status", progress=f"章节切分完成（{len(bounds)} 章）")
        return {"stage": "stage0"}

    # ---- stage1：map 并行逐章提取 ----

    async def _extract_one(chapter_no: int, text: str) -> tuple[int, str, list[str]]:
        """单章提取（LLM 调用并行 / demo 同步计算），不碰会话——返回结果由外层顺序落库。"""
        runtime.check_cancel()
        if await runtime.factory.available("low"):
            prompt = reg.build_prompt({
                "system": reg.render("system/base"),
                "project": "【拆文】逐章情节点提取",
                "tracking": f"【章节】第 {chapter_no} 章",
                "task": "请提取本章摘要、情节点、情绪与钩子。",
                "tail": f"【本章正文】\n{text[:4000]}",
            })
            model = await generate_checked(
                runtime.factory, "low", prompt, OutputContract(ChapterExtraction), task_type="chapter_extractor"
            )
            return chapter_no, model.summary, model.beats + (model.hooks or [])
        stub = extract_chapter(text, chapter_no)
        return chapter_no, stub["summary"], stub["beats"] + stub["hooks"]

    async def extract(state: AnalyzeState) -> AnalyzeState:
        runtime.check_cancel()
        if await svc.stage_status(book_id, "stage1") == "done":
            runtime.emit("status", progress="stage1 已完成，跳过逐章提取")
            return {"stage": "stage1"}
        runtime.emit("stage", stage="extract")
        texts, _titles = await _chapter_texts()
        # map 并行：LLM 调用按 MAX_BATCH_PARALLEL 分批 gather；会话只在顺序落库时触碰
        for i in range(0, len(texts), MAX_BATCH_PARALLEL):
            batch = texts[i : i + MAX_BATCH_PARALLEL]
            results = await asyncio.gather(*[_extract_one(i + j + 1, text) for j, text in enumerate(batch)])
            for chapter_no, summary, beats in results:
                runtime.check_cancel()
                await svc.update_chapter(book_id, chapter_no, summary=summary, beats=beats)
                runtime.emit("status", progress=f"已提取第 {chapter_no} 章")
        await svc.mark_stage(book_id, "stage1")
        await db.commit()
        runtime.emit("status", progress=f"逐章提取完成（{len(texts)} 章）")
        return {"stage": "stage1"}

    # ---- stage2-5：聚合 ----

    async def _aggregate_stage(state: AnalyzeState, stage: str) -> AnalyzeState:
        runtime.check_cancel()
        if await svc.stage_status(book_id, stage) == "done":
            runtime.emit("status", progress=f"{stage} 已完成，跳过")
            return {"stage": stage}
        runtime.emit("stage", stage=f"aggregate:{stage}")
        kinds = STAGE_KINDS[stage]
        texts, _titles = await _chapter_texts()
        full_text = "\n".join(texts)
        for kind in kinds:
            runtime.check_cancel()
            if await runtime.factory.available("high"):
                prompt = reg.build_prompt({
                    "system": reg.render("system/base"),
                    "project": f"【拆文】整书聚合分析",
                    "tracking": f"【维度】{kind}",
                    "task": "请产出该维度的分析文本。",
                    "tail": f"【全书文本】\n{full_text[:12000]}",
                })
                model = await generate_checked(
                    runtime.factory, "high", prompt, OutputContract(AnalysisOut), task_type="analysis_aggregate"
                )
                content = model.analysis
            else:
                content = AGGREGATORS[kind](full_text)
            await svc.upsert_aggregate(book_id, kind, content)
            runtime.emit("status", progress=f"{stage}：{kind} 已落库")
        await svc.mark_stage(book_id, stage)
        await db.commit()
        return {"stage": stage}

    def make_aggregate(stage: str):
        async def node(state: AnalyzeState) -> AnalyzeState:
            return await _aggregate_stage(state, stage)

        return node

    # ---- stage6：总报告 + 收尾 ----

    async def finalize(state: AnalyzeState) -> AnalyzeState:
        runtime.check_cancel()
        runtime.emit("stage", stage="report")
        book = await _book()
        texts, _titles = await _chapter_texts()
        # 汇总已落库聚合作为报告素材
        agg_rows = await db.scalars(
            select(AnalysisAggregate).where(AnalysisAggregate.book_id == book_id)
        )
        aggregates = {a.kind: a.content or "" for a in agg_rows}
        context = "\n\n".join(f"【{k}】\n{v}" for k, v in aggregates.items()) or "（暂无分维聚合）"

        if await svc.stage_status(book_id, "stage6") == "done":
            runtime.emit("status", progress="stage6 已完成，跳过")
            await svc.set_status(book_id, "done")
            await db.commit()
            return {"stage": "stage6"}

        if await runtime.factory.available("high"):
            prompt = reg.build_prompt({
                "system": reg.render("system/base"),
                "project": f"【拆文】整书总报告",
                "tracking": f"【书】{book.title}（{book.genre or ''}）",
                "task": "请生成一份完整的拆文总报告。",
                "tail": f"【各维聚合】\n{context[:12000]}",
            })
            model = await generate_checked(
                runtime.factory, "high", prompt, OutputContract(AnalysisOut), task_type="analysis_report"
            )
            report = model.analysis
        else:
            report = aggregate_report(book.title, texts, aggregates)
        await svc.upsert_aggregate(book_id, "report", report)
        await svc.mark_stage(book_id, "stage6")
        await svc.set_status(book_id, "done")
        await db.commit()
        runtime.emit("checkpoint", book_id=book_id, status="done", aggregates=len(aggregates) + 1)
        runtime.emit("status", progress="拆文完成")
        return {"stage": "stage6"}

    # ---- 装配 ----

    graph = StateGraph(AnalyzeState)
    graph.add_node("boundaries", boundaries)
    graph.add_node("extract", extract)
    for stage in ("stage2", "stage3", "stage4", "stage5"):
        graph.add_node(stage, make_aggregate(stage))
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "boundaries")
    graph.add_edge("boundaries", "extract")
    graph.add_edge("extract", "stage2")
    graph.add_edge("stage2", "stage3")
    graph.add_edge("stage3", "stage4")
    graph.add_edge("stage4", "stage5")
    graph.add_edge("stage5", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()
