"""章节提交并发锁（D11：US-29）。

- PG：`pg_advisory_xact_lock(project_key)` 在提交事务内串行化同一项目的章节提交，
  随事务提交/回滚自动释放（配合 TrackingService 的 `SELECT ... FOR UPDATE` 双保险）。
- SQLite（测试）：进程内 asyncio.Lock（按事件循环 + project_id 分桶），语义等价，保证测试覆盖并发。
- Redis（可选）：`chapter_redis_lock` 双重保险，仅在实际启用 RedisStore 时生效。
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.store import RedisStore, get_store, new_lock_token


class LockBusy(Exception):
    """并发提交冲突：同一资源正被其他提交持锁。"""


def project_lock_key(project_id: int) -> int:
    """project_id → [0, 2^63) 的 PG advisory lock 键（BIGINT 域）。"""
    digest = hashlib.md5(f"chapter:{project_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


# 进程内锁：key=(事件循环 id, project_id) —— 隔离不同测试循环，单循环内并发正确
_inproc_locks: dict[tuple[int, int], asyncio.Lock] = {}


async def _inproc_lock(project_id: int) -> asyncio.Lock:
    loop_id = id(asyncio.get_running_loop())
    key = (loop_id, project_id)
    lock = _inproc_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _inproc_locks[key] = lock
    return lock


@contextlib.asynccontextmanager
async def chapter_commit_lock(db: AsyncSession, project_id: int) -> AsyncIterator[None]:
    """同一项目章节提交的互斥临界区（PG advisory / SQLite 进程内锁）。"""
    dialect = db.bind.dialect.name if db.bind is not None else "sqlite"
    if dialect == "postgresql":
        await db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": project_lock_key(project_id)},
        )
        try:
            yield  # xact 锁随事务提交/回滚自动释放
        finally:
            pass
    else:
        lock = await _inproc_lock(project_id)
        async with lock:
            yield


@contextlib.asynccontextmanager
async def chapter_redis_lock(project_id: int, chapter_no: int) -> AsyncIterator[None]:
    """Redis 双重保险锁（可选）：仅当实际启用 RedisStore 时生效，否则空操作。

    键空间：`lock:chapter:{pid}:{no}`，ttl 60s，token 比较式释放。
    """
    store = get_store()
    if not isinstance(store, RedisStore):
        yield
        return
    key = f"lock:chapter:{project_id}:{chapter_no}"
    token = new_lock_token()
    if not await store.acquire_lock(key, token, ttl=60):
        raise LockBusy(f"章节 {chapter_no} 正被并发提交，请稍后重试")
    try:
        yield
    finally:
        await store.release_lock(key, token)
