from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, bigint_pk_type, jsonb


class ChapterReview(Base, TimestampMixin):
    """审查结果（full/lean/solo × 4 reviewer findings + 汇总）。"""

    __tablename__ = "chapter_reviews"
    __table_args__ = (UniqueConstraint("project_id", "chapter_no", "mode", name="uq_chapter_reviews_proj_no_mode"),)

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    chapter_no: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(16))  # full/lean/solo
    score: Mapped[int] = mapped_column(Integer, default=0)
    verdict: Mapped[str] = mapped_column(String(64))
    findings: Mapped[list | None] = mapped_column(jsonb(), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class DeslopRun(Base, TimestampMixin):
    """去味运行结果（定级 + findings + 改写前后正文）。

    改写正文存 original/rewritten 两列，不动 chapters 表（该表 project_id+chapter_no 唯一，
    无法同时存在 committed 与 draft 两行）；用户确认后 accept API 把 rewritten 写回 committed 行。
    """

    __tablename__ = "deslop_runs"
    __table_args__ = (UniqueConstraint("project_id", "chapter_no", name="uq_deslop_runs_proj_no"),)

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    chapter_no: Mapped[int] = mapped_column(Integer)
    grade: Mapped[str] = mapped_column(String(4))
    score: Mapped[int] = mapped_column(Integer, default=0)
    findings: Mapped[list | None] = mapped_column(jsonb(), nullable=True)
    original: Mapped[str | None] = mapped_column(Text, nullable=True)
    rewritten: Mapped[str | None] = mapped_column(Text, nullable=True)
