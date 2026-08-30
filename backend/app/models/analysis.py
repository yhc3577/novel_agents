from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, bigint_pk_type, jsonb


class AnalysisBook(Base, TimestampMixin):
    """拆文书（上传原文）。"""

    __tablename__ = "analysis_books"

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(128))
    genre: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")


class AnalysisChapter(Base, TimestampMixin):
    __tablename__ = "analysis_chapters"
    __table_args__ = (UniqueConstraint("book_id", "chapter_no", name="uq_analysis_chapters_book_no"),)

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("analysis_books.id"), index=True)
    chapter_no: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    beats: Mapped[dict | None] = mapped_column(jsonb(), nullable=True)


class AnalysisAggregate(Base, TimestampMixin):
    """拆文聚合（plot/rhythm/emotion/settings/characters/relations/report/style/golden）。"""

    __tablename__ = "analysis_aggregates"
    __table_args__ = (UniqueConstraint("book_id", "kind", name="uq_analysis_aggregates_book_kind"),)

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("analysis_books.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)


class AnalysisProgress(Base, TimestampMixin):
    __tablename__ = "analysis_progress"
    __table_args__ = (UniqueConstraint("book_id", "stage", name="uq_analysis_progress_book_stage"),)

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("analysis_books.id"), index=True)
    stage: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="pending")


class ScanResult(Base, TimestampMixin):
    """扫榜结果快照。"""

    __tablename__ = "scan_results"

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    raw: Mapped[dict | None] = mapped_column(jsonb(), nullable=True)
    cleaned: Mapped[dict | None] = mapped_column(jsonb(), nullable=True)
    report: Mapped[str | None] = mapped_column(Text, nullable=True)
