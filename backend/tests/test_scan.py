"""D9 验收：扫榜（US-24/25）。

- ScanGraph：collect→clean→validate→trends→decision→report→save，两平台各落一条 ScanResult；
- stub_scan：清洗/质量过滤/趋势/选题为确定性计算；
- HTTP：跑扫榜任务 → 每平台最新快照展示分布/热词/选题。
"""

import asyncio

from sqlalchemy import select

import app.models  # noqa: F401
from app.graphs.ctx import GraphRuntime
from app.graphs.scan import build_scan_graph
from app.graphs.stub_scan import (
    analyze_trends,
    clean_books,
    collect_rankings,
    generate_report,
    topic_decision,
    validate_quality,
)
from app.models import ScanResult, User


async def make_user(db):
    user = User(username="scan_user", password_hash="x", display_name="scan")
    db.add(user)
    await db.commit()
    return user


def test_collect_returns_structured_books():
    books = collect_rankings("qidian")
    assert len(books) == 20
    assert all(b["rank"] >= 1 and b["words"] > 0 and b["tags"] for b in books)
    assert collect_rankings("fanqie")[0]["genre"] == "都市"


def test_clean_and_validate():
    books = collect_rankings("fanqie")
    cleaned, dropped = clean_books(books)
    assert dropped == 0 and len(cleaned) == 20
    valid, invalid = validate_quality(cleaned)
    # 全部满足字数/评分门槛
    assert len(invalid) == 0 and len(valid) == 20
    # 手动制造低质条目验证过滤
    dirty = [dict(cleaned[0], words=3), dict(cleaned[1], rating=6.0)]
    valid2, invalid2 = validate_quality(dirty)
    assert len(invalid2) == 2 and len(valid2) == 0


def test_analyze_trends_shapes():
    books = collect_rankings("qidian")
    stats = analyze_trends(books)
    assert stats["total"] == 20
    assert stats["hot_tags"] and stats["top_books"][:1]
    # 分布按增速降序
    dist = stats["genre_distribution"]
    assert all(dist[i]["avg_growth"] >= dist[i + 1]["avg_growth"] for i in range(len(dist) - 1))
    # 热度最高的标签应稳定出现
    assert stats["hot_tags"][0]["count"] >= 1


def test_topic_decision_fields():
    books = collect_rankings("fanqie")
    stats = analyze_trends(books)
    dec = topic_decision(stats, books)
    assert dec["topic"] and dec["genre"] in {b["genre"] for b in books}
    assert dec["hot_tag"] and len(dec["hooks"]) >= 2 and dec["risk"]
    report = generate_report("fanqie", stats, dec)
    assert "选题决策" in report and dec["topic"] in report


async def test_scan_graph_demo(db):
    user = await make_user(db)
    queue = asyncio.Queue()
    runtime = GraphRuntime(db=db, user_id=user.id, project_id=0, task_id=501, emit=queue.put_nowait)
    await build_scan_graph(runtime).ainvoke({"user_id": user.id, "task_id": 501, "platforms": ["qidian", "fanqie"]})

    rows = (await db.scalars(select(ScanResult).where(ScanResult.owner_id == user.id))).all()
    assert {r.platform for r in rows} == {"qidian", "fanqie"}
    for r in rows:
        assert r.raw and r.cleaned and r.report
        assert r.cleaned["stats"]["total"] == 20
        assert r.cleaned["topic_decision"]["topic"]
        assert "选题决策" in r.report

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    types = [e["type"] for e in events]
    assert "stage" in types and "tool" in types and "checkpoint" in types
    tools = {e.get("tool") for e in events if e["type"] == "tool"}
    assert {"scan:collect:qidian", "scan:collect:fanqie"} <= tools


async def test_api_scan_flow(client, db_engine):
    """HTTP 验收：跑扫榜 → latest 展示两平台快照与选题。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    r = await client.post("/api/auth/register", json={"username": "scan_api", "password": "secret123"})
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = await client.post("/api/scan/runs", json={}, headers=auth)
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    for _ in range(300):
        st = (await client.get(f"/api/tasks/{tid}", headers=auth)).json()["status"]
        if st in ("success", "failed"):
            break
        await asyncio.sleep(0.05)
    assert st == "success"

    latest = (await client.get("/api/scan/latest", headers=auth)).json()
    platforms = latest["platforms"]
    assert {p["platform"] for p in platforms} == {"qidian", "fanqie"}
    snap = next(p for p in platforms if p["platform"] == "qidian")
    assert snap["cleaned"]["stats"]["total"] == 20
    assert snap["cleaned"]["topic_decision"]["topic"]
    assert "选题决策" in snap["report"]

    history = (await client.get("/api/scan/results?platform=fanqie", headers=auth)).json()
    assert len(history) == 1 and history[0]["platform"] == "fanqie"
