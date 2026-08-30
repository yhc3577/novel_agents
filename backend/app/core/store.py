"""Redis 预留接口 + PG 回源实现 + 可禁用（D11：US-28）。

- `MemoryStore`（Protocol）：业务只依赖协议；切 Redis 只换 `get_store()` 的返回，业务零改动。
- `PGMemoryStore`：默认实现，全部操作走 PG（`kv_cache` / `kv_locks` 表）——Redis 关闭时功能等价。
- `RedisStore`：`config.redis_url` 非空时启用（键空间见详细设计 §9）。
- `NullStore`：`config.kv_cache_enabled=false` 时全 no-op，功能等价但无缓存。
- `FLUSHDB` 永远安全：缓存可回填（业务侧按需回源重建）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db.engine import SessionLocal
from app.models.kv import KvCache, KvLock


@runtime_checkable
class MemoryStore(Protocol):
    """KV 存储 + 分布式锁的抽象协议。"""

    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int | None = None) -> None: ...
    async def delete_prefix(self, prefix: str) -> int: ...
    async def acquire_lock(self, key: str, token: str, ttl: int) -> bool: ...
    async def release_lock(self, key: str, token: str) -> None: ...


def _aware(dt: datetime) -> datetime:
    """SQLite 回读的 tz-aware 列可能是 naive，统一视为 UTC。"""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


class NullStore:
    """缓存禁用时的空实现：读返回 None，锁直接放行（功能等价）。"""

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        return None

    async def delete_prefix(self, prefix: str) -> int:
        return 0

    async def acquire_lock(self, key: str, token: str, ttl: int) -> bool:
        return True

    async def release_lock(self, key: str, token: str) -> None:
        return None


class PGMemoryStore:
    """PG 回源实现：`kv_cache` 做缓存，`kv_locks` 做互斥锁（token 防误删、过期可接管）。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    async def get(self, key: str) -> str | None:
        async with self._sf() as db:
            row = await db.scalar(select(KvCache).where(KvCache.key == key))
            if row is None:
                return None
            if row.expires_at is not None and _aware(row.expires_at) <= datetime.now(timezone.utc):
                await db.delete(row)
                await db.commit()
                return None
            return row.value

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl) if ttl else None
        async with self._sf() as db:
            row = await db.scalar(select(KvCache).where(KvCache.key == key))
            if row is None:
                db.add(KvCache(key=key, value=value, expires_at=expires))
            else:
                row.value = value
                row.expires_at = expires
            await db.commit()

    async def delete_prefix(self, prefix: str) -> int:
        async with self._sf() as db:
            result = await db.execute(delete(KvCache).where(KvCache.key.like(f"{prefix}%")))
            await db.commit()
            return result.rowcount or 0

    async def acquire_lock(self, key: str, token: str, ttl: int) -> bool:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl)
        async with self._sf() as db:
            row = await db.scalar(select(KvLock).where(KvLock.key == key))
            if row is None:
                db.add(KvLock(key=key, token=token, expires_at=expires))
                await db.commit()
                return True
            if _aware(row.expires_at) <= now:
                # 过期锁可接管（避免死锁）
                row.token = token
                row.expires_at = expires
                await db.commit()
                return True
            return False

    async def release_lock(self, key: str, token: str) -> None:
        async with self._sf() as db:
            await db.execute(delete(KvLock).where(KvLock.key == key, KvLock.token == token))
            await db.commit()


class RedisStore:
    """Redis 实现（`config.redis_url` 非空时启用）。仅需 redis-py（惰性导入）。"""

    def __init__(self, url: str):
        from redis import asyncio as aioredis  # 未装 redis 时不阻塞其余功能

        self._r = aioredis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        return await self._r.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        if ttl:
            await self._r.set(key, value, ex=ttl)
        else:
            await self._r.set(key, value)

    async def delete_prefix(self, prefix: str) -> int:
        keys = [key async for key in self._r.scan_iter(match=f"{prefix}*")]
        if keys:
            return await self._r.delete(*keys)
        return 0

    async def acquire_lock(self, key: str, token: str, ttl: int) -> bool:
        return bool(await self._r.set(key, token, nx=True, ex=ttl))

    async def release_lock(self, key: str, token: str) -> None:
        # Lua：仅当 token 匹配才删除，防止误删他人持有的锁
        lua = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        end
        return 0
        """
        await self._r.eval(lua, 1, key, token)


_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    """按配置返回唯一的存储实例：NullStore（禁用）→ RedisStore → PGMemoryStore（默认）。"""
    global _store
    if _store is None:
        settings = get_settings()
        if not settings.kv_cache_enabled:
            _store = NullStore()
        elif settings.redis_url:
            _store = RedisStore(settings.redis_url)
        else:
            _store = PGMemoryStore(SessionLocal)
    return _store


def reset_store() -> None:
    """清空缓存的 store 实例（测试换配置 / 热切换用）。"""
    global _store
    _store = None


def new_lock_token() -> str:
    return uuid4().hex
