from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, bigint_pk_type, jsonb


class Setting(Base, TimestampMixin):
    """设定（关系/题材定位/题材正文提示卡/世界观/金手指/势力）。"""

    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("project_id", "kind", "title", name="uq_settings_project_kind_title"),)

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)


class Volume(Base, TimestampMixin):
    __tablename__ = "volumes"
    __table_args__ = (UniqueConstraint("project_id", "no", name="uq_volumes_project_no"),)

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(128))
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)


class OutlineChapter(Base, TimestampMixin):
    """大纲章节（细纲情节点）。"""

    __tablename__ = "outline_chapters"
    __table_args__ = (UniqueConstraint("volume_id", "chapter_no", name="uq_outline_chapters_volume_no"),)

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    volume_id: Mapped[int] = mapped_column(ForeignKey("volumes.id"), index=True)
    chapter_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(128))
    beats: Mapped[dict | None] = mapped_column(jsonb(), nullable=True)  # 细纲情节点
    contract_status: Mapped[str] = mapped_column(String(16), default="valid")  # valid/invalid


class Chapter(Base, TimestampMixin):
    """正文章节。"""

    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("project_id", "chapter_no", name="uq_chapters_project_no"),)

    id: Mapped[int] = mapped_column(bigint_pk_type(), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    volume_id: Mapped[int | None] = mapped_column(ForeignKey("volumes.id"), nullable=True)
    chapter_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    wordcount: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/committed
    revision: Mapped[int] = mapped_column(Integer, default=0)
