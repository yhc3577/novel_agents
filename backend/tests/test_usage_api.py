"""D10 验收（US-27）：用量统计 API——按天 token/成本/缓存命中率汇总。"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import UsageLog


async def _seed_usage(db_engine, user_id: int, days_ago: int = 0, **kw):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sf() as s:
        s.add(
            UsageLog(
                owner_id=user_id,
                provider=kw.get("provider", "deepseek"),
                model=kw.get("model", "deepseek-chat"),
                task_type=kw.get("task_type", "write_chapter"),
                prompt_tokens=kw.get("prompt_tokens", 100),
                completion_tokens=kw.get("completion_tokens", 50),
                cached_tokens=kw.get("cached_tokens", 30),
                cost_estimate=kw.get("cost", Decimal("0.001")),
                created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
            )
        )
        await s.commit()


async def _uid(client, auth):
    me = (await client.get("/api/auth/me", headers=auth)).json()
    return me["id"]


async def test_usage_api_aggregation(client, db_engine):
    r = await client.post("/api/auth/register", json={"username": "usg_api", "password": "secret123"})
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    uid = await _uid(client, auth)

    # 同一用户 3 条用量（分布在两天）
    await _seed_usage(db_engine, uid, days_ago=0, prompt_tokens=100, completion_tokens=50, cached_tokens=30,
                      task_type="write_chapter", cost=Decimal("0.001"))
    await _seed_usage(db_engine, uid, days_ago=0, prompt_tokens=200, completion_tokens=100, cached_tokens=0,
                      task_type="review", cost=Decimal("0.002"))
    await _seed_usage(db_engine, uid, days_ago=1, prompt_tokens=50, completion_tokens=25, cached_tokens=25,
                      task_type="write_chapter", cost=Decimal("0.0005"))

    resp = (await client.get("/api/usage?days=7", headers=auth)).json()
    assert resp["totals"]["calls"] == 3
    assert resp["totals"]["prompt_tokens"] == 350
    assert resp["totals"]["completion_tokens"] == 175
    assert resp["totals"]["cached_tokens"] == 55
    assert abs(resp["totals"]["cost"] - 0.0035) < 1e-6
    # 缓存命中率 = 55 / 525
    assert abs(resp["totals"]["cache_hit_rate"] - 55 / 525) < 1e-4

    assert len(resp["daily"]) == 2  # 两天
    # 按 token 降序：review=300 > write_chapter=225
    assert resp["by_task_type"][0]["task_type"] == "review"
    assert resp["by_task_type"][1]["task_type"] == "write_chapter"
    assert resp["by_task_type"][1]["calls"] == 2
    assert resp["by_provider"][0]["provider"] == "deepseek"

    # 空结果：另一个用户看不到
    r2 = await client.post("/api/auth/register", json={"username": "usg_api2", "password": "secret123"})
    auth2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    resp2 = (await client.get("/api/usage?days=7", headers=auth2)).json()
    assert resp2["totals"]["calls"] == 0 and resp2["daily"] == []


async def test_usage_api_days_filter(client, db_engine):
    r = await client.post("/api/auth/register", json={"username": "usg_api3", "password": "secret123"})
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    uid = await _uid(client, auth)
    await _seed_usage(db_engine, uid, days_ago=5, prompt_tokens=10, completion_tokens=5)
    await _seed_usage(db_engine, uid, days_ago=1, prompt_tokens=20, completion_tokens=10)

    resp1 = (await client.get("/api/usage?days=2", headers=auth)).json()
    assert resp1["totals"]["calls"] == 1 and resp1["totals"]["prompt_tokens"] == 20
    resp7 = (await client.get("/api/usage?days=7", headers=auth)).json()
    assert resp7["totals"]["calls"] == 2
