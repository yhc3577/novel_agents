from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, bigint_pk_type, jsonb


class TrackingState(Base, TimestampMixin):
    """追踪唯一真值（含版本守卫）。只能由 TrackingService/ChapterService 写入。"""

    __tablename__ = "tracking_state"

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), unique=True)
    state_revision: Mapped[int] = mapped_column(Integer, default=0)  # 版本守卫
    last_committed_chapter: Mapped[int] = mapped_column(Integer, default=0)
    state_jsonb: Mapped[dict | None] = mapped_column(jsonb(), nullable=True)


class Character(Base, TimestampMixin):
    __tablename__ = "characters"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_characters_project_name"),)

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    profile: Mapped[dict | None] = mapped_column(jsonb(), nullable=True)
    active_status: Mapped[str | None] = mapped_column(String(16), nullable=True)


class Foreshadowing(Base, TimestampMixin):
    __tablename__ = "foreshadowing"

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    planted_chapter: Mapped[int] = mapped_column(Integer)
    resolved_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="planted")  # planted/resolved


class TimelineEvent(Base, TimestampMixin):
    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    chapter_no: Mapped[int] = mapped_column(Integer)
    author_only: Mapped[bool] = mapped_column(Boolean, default=False)
    content: Mapped[str] = mapped_column(Text)


class ChapterRecord(Base, TimestampMixin):
    """派生：仅提交事务重建。"""

    __tablename__ = "chapter_records"
    __table_args__ = (UniqueConstraint("project_id", "chapter_no", name="uq_chapter_records_project_no"),)

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    chapter_no: Mapped[int] = mapped_column(Integer)
    context: Mapped[dict | None] = mapped_column(jsonb(), nullable=True)
    characters: Mapped[dict | None] = mapped_column(jsonb(), nullable=True)
    events: Mapped[dict | None] = mapped_column(jsonb(), nullable=True)
    foreshadowing: Mapped[dict | None] = mapped_column(jsonb(), nullable=True)


class ContextView(Base, TimestampMixin):
    """派生：固定 7 列 ≤12KB，键 {project_id, revision}。"""

    __tablename__ = "context_views"

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), unique=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuthorMemory(Base, TimestampMixin):
    """作者记忆（按用户，跨项目）。"""

    __tablename__ = "author_memory"

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Benchmark(Base, TimestampMixin):
    __tablename__ = "benchmarks"

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    book_title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)


class ReferenceMaterial(Base, TimestampMixin):
    __tablename__ = "reference_materials"

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text)
    kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
