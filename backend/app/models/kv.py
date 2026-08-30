"""KV 缓存 / 互斥锁表（D11：US-28 Redis 预留接口的 PG 回源实现）。

- kv_cache：`get/set/delete_prefix` 的落点，带 TTL，`FLUSHDB` 等价 = delete_prefix 清空可回填。
- kv_locks：`acquire_lock/release_lock` 的落点（进程/实例间互斥，token 防误删）。
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KvCache(Base):
    """KV 缓存行。expires_at 为空 = 永不过期。"""

    __tablename__ = "kv_cache"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KvLock(Base):
    """互斥锁行。仅持有者 token 可释放；过期后可被接管。"""

    __tablename__ = "kv_locks"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
