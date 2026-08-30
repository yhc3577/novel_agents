"""ImportGraph（D7：US-20）：拆解完成的书 → 可写项目。

链路：validate（幂等检查）→ migrate_structure（卷+细纲）→ import_content（正文入库）
    → tracking_init（追踪初始化+游标）→ activate（设活跃书 + 书标记 imported）。

同步执行（快、无流式），由 API 在请求内 `graph.ainvoke`；slug 用 imp-{book_id}
保证按 owner+slug 幂等——重复导入直接返回既有项目。
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select, update

from app.graphs.stub_analysis import split_chapters
from app.models import AnalysisBook, AnalysisChapter, Chapter, OutlineChapter, Project, TrackingState, Volume
from app.services.tracking import TrackingService
from app.services.wordcount import measure_text

IMPORT_SLUG_PREFIX = "imp-"


class ImportState(TypedDict, total=False):
    user_id: int
    book_id: int
    project_id: int | None
    slug: str | None
    title: str | None
    genre: str | None
    imported: bool


def build_import_graph(runtime):
    db = runtime.db
    user_id = runtime.user_id

    async def validate(state: ImportState) -> ImportState:
        book = await db.get(AnalysisBook, state["book_id"])
        if book is None or book.owner_id != user_id:
            raise ValueError("拆文书不存在")
        slug = f"{IMPORT_SLUG_PREFIX}{book.id}"
        existing = await db.scalar(
            select(Project).where(Project.owner_id == user_id, Project.slug == slug)
        )
        if existing is not None:
            # 幂等：已导入过（无论书状态是否仍为 done）直接返回既有项目
            return {"project_id": existing.id, "slug": slug, "title": existing.title, "imported": True}
        if book.status != "done":
            raise ValueError("请先完成拆解再一键导入")
        return {"slug": slug, "title": book.title, "genre": book.genre, "imported": False}

    async def migrate_structure(state: ImportState) -> ImportState:
        if state["imported"]:
            return {}
        book = await db.get(AnalysisBook, state["book_id"])
        project = Project(owner_id=user_id, slug=state["slug"], title=state["title"], genre=state.get("genre"), status="inactive")
        db.add(project)
        await db.flush()
        vol = Volume(project_id=project.id, no=1, title="第一卷·导入")
        db.add(vol)
        await db.flush()
        chapters = await db.scalars(
            select(AnalysisChapter).where(AnalysisChapter.book_id == state["book_id"]).order_by(AnalysisChapter.chapter_no)
        )
        for c in chapters:
            db.add(
                OutlineChapter(
                    volume_id=vol.id,
                    chapter_no=c.chapter_no,
                    title=f"第{c.chapter_no}章",
                    beats={"summary": c.summary or "", "beats": c.beats or []},
                )
            )
        await db.flush()
        return {"project_id": project.id}

    async def import_content(state: ImportState) -> ImportState:
        if state["imported"]:
            return {}
        book = await db.get(AnalysisBook, state["book_id"])
        bounds = split_chapters(book.source_text or "")
        for b in bounds:
            text = (book.source_text[b["start"] : b["end"]]).strip()
            db.add(
                Chapter(
                    project_id=state["project_id"],
                    volume_id=None,
                    chapter_no=b["no"],
                    title=b["title"],
                    content=text,
                    wordcount=measure_text(text),
                    status="committed",
                    revision=1,
                )
            )
        await db.flush()
        return {}

    async def tracking_init(state: ImportState) -> ImportState:
        if state["imported"]:
            return {}
        pid = state["project_id"]
        await TrackingService(db).init(pid, {"seed": "一键导入初始化"})
        committed = (await db.scalars(select(Chapter).where(Chapter.project_id == pid, Chapter.status == "committed"))).all()
        ts = await db.scalar(select(TrackingState).where(TrackingState.project_id == pid))
        ts.last_committed_chapter = len(committed)
        await db.flush()
        return {}

    async def activate(state: ImportState) -> ImportState:
        if state["imported"]:
            return {}
        pid = state["project_id"]
        # 设为活跃书：其余项目置 inactive（与 ProjectRepository.activate 同语义）
        await db.execute(update(Project).where(Project.owner_id == user_id).values(status="inactive"))
        project = await db.get(Project, pid)
        project.status = "active"
        book = await db.get(AnalysisBook, state["book_id"])
        book.status = "imported"
        await db.commit()
        return {}

    graph = StateGraph(ImportState)
    graph.add_node("validate", validate)
    graph.add_node("migrate_structure", migrate_structure)
    graph.add_node("import_content", import_content)
    graph.add_node("tracking_init", tracking_init)
    graph.add_node("activate", activate)
    graph.add_edge(START, "validate")
    graph.add_edge("validate", "migrate_structure")
    graph.add_edge("migrate_structure", "import_content")
    graph.add_edge("import_content", "tracking_init")
    graph.add_edge("tracking_init", "activate")
    graph.add_edge("activate", END)
    return graph.compile()
