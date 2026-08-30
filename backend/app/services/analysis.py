"""拆文服务（D6：US-18）：书 CRUD + 章节/聚合落库 + 断点进度读写。

写路径全部在 AnalyzeGraph 节点内调用；读路径给 API 层用。
断点恢复依赖 analysis_progress：节点在跑之前查 stage_status，done 则跳过。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnalysisAggregate, AnalysisBook, AnalysisChapter, AnalysisProgress

# 阶段 → 聚合 kind 映射（stage2..stage6 各落一类或多类 analysis_aggregates）
STAGE_KINDS: dict[str, list[str]] = {
    "stage2": ["plot", "rhythm"],
    "stage3": ["emotion", "characters"],
    "stage4": ["settings", "relations"],
    "stage5": ["style", "golden"],
    "stage6": ["report"],
}
ALL_KINDS: list[str] = [k for kinds in STAGE_KINDS.values() for k in kinds]


class AnalysisService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- 书 ----

    async def create_book(self, owner_id: int, *, title: str, genre: str | None = None, source_text: str | None = None) -> AnalysisBook:
        book = AnalysisBook(owner_id=owner_id, title=title, genre=genre, source_text=source_text, status="pending")
        self.db.add(book)
        await self.db.commit()
        await self.db.refresh(book)
        return book

    async def get_owned(self, owner_id: int, book_id: int) -> AnalysisBook | None:
        book = await self.db.get(AnalysisBook, book_id)
        if book is None or book.owner_id != owner_id:
            return None
        return book

    async def list_owned(self, owner_id: int) -> list[AnalysisBook]:
        rows = await self.db.scalars(
            select(AnalysisBook).where(AnalysisBook.owner_id == owner_id).order_by(AnalysisBook.id.desc())
        )
        return list(rows)

    async def snapshot(self, owner_id: int, book_id: int) -> dict | None:
        """书 + 章节 + 聚合 + 进度 一次性快照（拆文页展示用）。"""
        book = await self.get_owned(owner_id, book_id)
        if book is None:
            return None
        chapters = await self.db.scalars(
            select(AnalysisChapter).where(AnalysisChapter.book_id == book_id).order_by(AnalysisChapter.chapter_no)
        )
        aggregates = await self.db.scalars(select(AnalysisAggregate).where(AnalysisAggregate.book_id == book_id))
        progress = await self.db.scalars(select(AnalysisProgress).where(AnalysisProgress.book_id == book_id))
        return {
            "id": book.id,
            "title": book.title,
            "genre": book.genre,
            "status": book.status,
            "chapters": [
                {"chapter_no": c.chapter_no, "summary": c.summary, "beats": c.beats} for c in chapters
            ],
            "aggregates": {a.kind: a.content for a in aggregates},
            "progress": {p.stage: p.status for p in progress},
        }

    async def set_status(self, book_id: int, status: str) -> None:
        book = await self.db.get(AnalysisBook, book_id)
        if book is not None:
            book.status = status
            await self.db.flush()

    # ---- 章节 ----

    async def ensure_chapters(self, book_id: int, chapters: list[dict]) -> None:
        """stage0：按边界幂等补齐 AnalysisChapter 行（summary/beats 不动，保断点）。"""
        for c in chapters:
            row = await self.db.scalar(
                select(AnalysisChapter).where(AnalysisChapter.book_id == book_id, AnalysisChapter.chapter_no == c["no"])
            )
            if row is None:
                self.db.add(AnalysisChapter(book_id=book_id, chapter_no=c["no"]))
        await self.db.flush()

    async def update_chapter(self, book_id: int, chapter_no: int, *, summary: str, beats: list[str]) -> None:
        row = await self.db.scalar(
            select(AnalysisChapter).where(AnalysisChapter.book_id == book_id, AnalysisChapter.chapter_no == chapter_no)
        )
        if row is None:
            self.db.add(AnalysisChapter(book_id=book_id, chapter_no=chapter_no, summary=summary, beats=beats))
        else:
            row.summary = summary
            row.beats = beats
        await self.db.flush()

    async def upsert_aggregate(self, book_id: int, kind: str, content: str) -> None:
        row = await self.db.scalar(
            select(AnalysisAggregate).where(AnalysisAggregate.book_id == book_id, AnalysisAggregate.kind == kind)
        )
        if row is None:
            self.db.add(AnalysisAggregate(book_id=book_id, kind=kind, content=content))
        else:
            row.content = content
        await self.db.flush()

    # ---- 进度（断点恢复）----

    async def stage_status(self, book_id: int, stage: str) -> str | None:
        row = await self.db.scalar(
            select(AnalysisProgress).where(AnalysisProgress.book_id == book_id, AnalysisProgress.stage == stage)
        )
        return row.status if row is not None else None

    async def mark_stage(self, book_id: int, stage: str, status: str = "done") -> None:
        row = await self.db.scalar(
            select(AnalysisProgress).where(AnalysisProgress.book_id == book_id, AnalysisProgress.stage == stage)
        )
        if row is None:
            self.db.add(AnalysisProgress(book_id=book_id, stage=stage, status=status))
        else:
            row.status = status
        await self.db.flush()
