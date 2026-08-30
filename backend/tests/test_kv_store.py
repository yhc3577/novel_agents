"""D11 验收（US-28/29）：Redis 预留接口 + PG 回源 + 禁用；章节提交项目级锁。

- PGMemoryStore：get/set/TTL/delete_prefix；acquire_lock/release_lock（token 防误删、过期接管）。
- NullStore：禁用时功能等价（读 None、锁放行）。
- get_store()：按配置选择 Null / Redis / PG。
- 章节提交并发：同一项目两个并发 commit 被串行化，revision 顺序推进，无脏状态。
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.models  # noqa: F401
from app.core import store as store_mod
from app.core.locks import chapter_commit_lock
from app.core.store import NullStore, PGMemoryStore
from app.models import Character, KvLock, OutlineChapter, Project, TrackingState, User, Volume
from app.services.tracking import TrackingService


@pytest.fixture
async def project(db):
    user = User(username="kv_user", password_hash="x", display_name="kv")
    db.add(user)
    await db.flush()
    proj = Project(owner_id=user.id, slug="kv-lock-book", title="并发锁测试书", genre="玄幻", status="active")
    db.add(proj)
    await db.flush()
    vol = Volume(project_id=proj.id, no=1, title="第一卷")
    db.add(vol)
    await db.flush()
    db.add(OutlineChapter(
        volume_id=vol.id, chapter_no=1, title="初入仙门",
        beats={"summary": "主角觉醒", "target_wordcount": 1000},
    ))
    await db.commit()
    return proj


# ---- US-28: KV 存储 ----

async def _pg_store(db_engine):
    return PGMemoryStore(async_sessionmaker(db_engine, expire_on_commit=False))


async def test_pg_store_set_get_delete(db_engine):
    st = await _pg_store(db_engine)
    assert await st.get("ctx:view:1:1") is None
    await st.set("ctx:view:1:1", "内容A")
    await st.set("ctx:view:1:2", "内容B")
    await st.set("mem:author:9:note", "备忘录")
    assert await st.get("ctx:view:1:1") == "内容A"
    assert await st.set("ctx:view:1:1", "内容A改") is None  # 覆盖
    assert await st.get("ctx:view:1:1") == "内容A改"
    # delete_prefix 清空一类键（等价 FLUSHDB 后回填）
    assert await st.delete_prefix("ctx:view:1:") == 2
    assert await st.get("ctx:view:1:2") is None
    assert await st.get("mem:author:9:note") == "备忘录"  # 其他前缀不受影响


async def test_pg_store_ttl_expiry(db_engine):
    st = await _pg_store(db_engine)
    await st.set("scan:qidian:now", "快照", ttl=3600)
    assert await st.get("scan:qidian:now") == "快照"
    # 直接改 expires_at 为过去，模拟过期
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sf() as s:
        row = await s.scalar(select(app.models.KvCache).where(app.models.KvCache.key == "scan:qidian:now"))
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await s.commit()
    assert await st.get("scan:qidian:now") is None  # 过期即失效


async def test_pg_store_lock_token_and_expiry(db_engine):
    st = await _pg_store(db_engine)
    key = "lock:chapter:3:1"
    assert await st.acquire_lock(key, "token-a", ttl=60) is True
    assert await st.acquire_lock(key, "token-b", ttl=60) is False  # 已持有，拒绝
    await st.release_lock(key, "token-wrong")  # 错误 token 不释放
    assert await st.acquire_lock(key, "token-c", ttl=60) is False
    await st.release_lock(key, "token-a")  # 持有者释放
    assert await st.acquire_lock(key, "token-d", ttl=60) is True

    # 过期锁可接管
    async with async_sessionmaker(db_engine, expire_on_commit=False)() as s:
        row = await s.scalar(select(KvLock).where(KvLock.key == key))
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await s.commit()
    assert await st.acquire_lock(key, "token-e", ttl=60) is True


async def test_null_store_functionally_equivalent(db):
    st = NullStore()
    assert await st.get("anything") is None
    assert await st.set("k", "v", ttl=10) is None
    assert await st.delete_prefix("p") == 0
    assert await st.acquire_lock("lock", "t", 10) is True  # 禁用时不阻塞提交
    assert await st.release_lock("lock", "t") is None


async def test_get_store_selection(monkeypatch):
    """kv_cache_enabled=false → NullStore；redis_url 非空 → RedisStore；否则 → PGMemoryStore。"""
    settings = store_mod.get_settings()
    store_mod.reset_store()

    monkeypatch.setattr(settings, "kv_cache_enabled", False)
    monkeypatch.setattr(settings, "redis_url", None)
    assert isinstance(store_mod.get_store(), NullStore)

    store_mod.reset_store()
    monkeypatch.setattr(settings, "kv_cache_enabled", True)
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6379/0")
    from app.core.store import RedisStore

    assert isinstance(store_mod.get_store(), RedisStore)

    store_mod.reset_store()
    monkeypatch.setattr(settings, "kv_cache_enabled", True)
    monkeypatch.setattr(settings, "redis_url", None)
    assert isinstance(store_mod.get_store(), PGMemoryStore)
    store_mod.reset_store()


# ---- US-29: 章节提交项目级锁 ----

async def test_chapter_commit_lock_serializes_coroutines(db, project):
    """项目级锁是互斥临界区：第二个进入者等待第一个释放。"""
    order: list[str] = []
    entered = asyncio.Event()

    async def worker(name: str, delay: float):
        async with chapter_commit_lock(db, project.id):
            order.append(name)
            entered.set()
            await asyncio.sleep(delay)
            order.append(f"{name}-done")

    t1 = asyncio.create_task(worker("A", 0.05))
    await entered.wait()  # A 已持锁
    t2 = asyncio.create_task(worker("B", 0.01))
    await asyncio.sleep(0.02)
    assert "B" not in order  # A 未释放前 B 无法进入
    await asyncio.gather(t1, t2)
    assert order == ["A", "A-done", "B", "B-done"]  # 严格串行


async def test_concurrent_commits_serialized(db, project):
    """同一项目两个并发章节提交被串行化：都成功、revision 顺序推进、无脏状态。"""
    svc = TrackingService(db)
    await svc.init(project.id, {})

    tx1 = {
        "chapter_no": 1,
        "characters": [{"name": "陈玄", "kind": "主角", "profile": {"出身": "猎户"}}],
        "foreshadowing": [{"content": "神秘玉佩异动"}],
        "timeline": [{"content": "陈玄自昏迷中醒来", "author_only": False}],
    }
    tx2 = {
        "chapter_no": 1,
        "characters": [{"name": "柳如烟", "kind": "女主", "profile": {"门派": "听雨楼"}}],
        "foreshadowing": [{"content": "铜镜裂纹蔓延"}],
        "timeline": [{"content": "柳如烟登场", "author_only": False}],
    }

    revs = await asyncio.gather(svc.commit(project.id, tx1), svc.commit(project.id, tx2))
    assert sorted(revs) == [2, 3]  # init=1 → 两次提交 → 2、3

    st = await db.scalar(select(TrackingState).where(TrackingState.project_id == project.id))
    assert st.state_revision == 3
    chars = (await db.scalars(select(Character).where(Character.project_id == project.id))).all()
    assert {c.name for c in chars} == {"陈玄", "柳如烟"}  # 两条角色的追踪都落库，无丢失
    assert (await svc.check(project.id))["views_consistent"] is True


async def test_concurrent_commits_same_chapter_conflict(db, project):
    """同一章节并发提交：expected_revision 乐观锁能拦截过期提交（在锁串行化之上兜底）。"""
    svc = TrackingService(db)
    await svc.init(project.id, {})
    await svc.commit(project.id, {
        "chapter_no": 1,
        "characters": [{"name": "陈玄", "kind": "主角", "profile": {}}],
        "foreshadowing": [],
        "timeline": [],
    })  # revision → 2
    from app.services.tracking import TrackingConflict

    with pytest.raises(TrackingConflict):
        await svc.commit(project.id, {
            "chapter_no": 1,
            "characters": [],
            "foreshadowing": [],
            "timeline": [],
        }, expected_revision=1)  # 实际已是 2
