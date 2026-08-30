from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, JSON, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def bigint_pk_type():
    """PG 用 BIGSERIAL；SQLite 仅对 INTEGER PRIMARY KEY 自增，测试环境需映射为 Integer。"""
    return BigInteger().with_variant(Integer, "sqlite")


def jsonb():
    """PG 用 JSONB；SQLite 无 JSONB，映射回通用 JSON（序列化行为一致）。"""
    return JSON().with_variant(JSONB, "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
