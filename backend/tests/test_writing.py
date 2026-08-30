"""D4 验收：写作闭环后端（US-12/13/14/15）。

验收点：
- POST /projects/{pid}/chapters/next 返回 task_id；
- SSE 事件流出现 stage→tool→token→checkpoint→done；
- 提交后 tracking_state 更新、chapters 出现 committed 行；
- 写图在 demo（无 key）模式下端到端可跑，日更循环有界。
"""

import asyncio
import json

from sqlalchemy import select

import app.models  # noqa: F401
from app.graphs.ctx import GraphRuntime
from app.graphs.write import build_write_graph
from app.models import Chapter, OutlineChapter, Project, TrackingState, User, Volume
from app.schemas.writing import IntentResult
from app.services.task_service import TaskService, registry


async def make_project(db, title="仙路初开", slug="xianlu-test", outline=True):
    user = User(username="w_user", password_hash="x", display_name="w")
    db.add(user)
    await db.flush()
    proj = Project(owner_id=user.id, slug=slug, title=title, genre="玄幻", status="active")
    db.add(proj)
    await db.flush()
    if outline:
        vol = Volume(project_id=proj.id, no=1, title="第一卷")
        db.add(vol)
        await db.flush()
        db.add(OutlineChapter(volume_id=vol.id, chapter_no=1, title="苏醒", beats={"summary": "主角觉醒金手指", "target_wordcount": 1000}))
        db.add(OutlineChapter(volume_id=vol.id, chapter_no=2, title="试炼", beats={"summary": "主角运用金手指应敌", "target_wordcount": 1000}))
    await db.commit()
    return proj, user


async def collect_events(queue):
    """图直接调用场景：图不产 done（由执行器补发），排空队列即可。"""
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


async def test_write_graph_demo_end_to_end(db):
    """demo（无 key）模式：写一章 → 提交 → 追踪/派生视图更新。"""
    proj, user = await make_project(db)
    queue = asyncio.Queue()
    runtime = GraphRuntime(db=db, user_id=user.id, project_id=proj.id, task_id=1, emit=queue.put_nowait)
    graph = build_write_graph(runtime)
    result = await graph.ainvoke(
        {
            "user_id": user.id,
            "project_id": proj.id,
            "task_id": 1,
            "action": "write_next",
            "scenario": "帮我写第一章",
        }
    )
    events = await collect_events(queue)
    types = [e["type"] for e in events]
    # 事件序列：stage → tool → token → checkpoint（done 由执行器补发，图直接调用不产）
    assert "stage" in types and "writing" in [e.get("stage") for e in events if e["type"] == "stage"]
    assert "tool" in types  # TrackingService.check / QualityService.full_gate
    assert "token" in types
    assert "checkpoint" in types

    ch = await db.scalar(select(Chapter).where(Chapter.project_id == proj.id, Chapter.chapter_no == 1))
    assert ch is not None and ch.status == "committed" and ch.wordcount >= 900
    st = await db.scalar(select(TrackingState).where(TrackingState.project_id == proj.id))
    assert st.state_revision == 2 and st.last_committed_chapter == 1
    from app.models import ContextView

    view = await db.scalar(select(ContextView).where(ContextView.project_id == proj.id))
    assert view is not None and view.revision == 2


async def test_write_graph_open_book_when_no_outline(db):
    """无细纲时自动开书（ensure_outline → 卷+细纲入库），再写第一章。"""
    proj, user = await make_project(db, outline=False)
    queue = asyncio.Queue()
    runtime = GraphRuntime(db=db, user_id=user.id, project_id=proj.id, task_id=2, emit=queue.put_nowait)
    graph = build_write_graph(runtime)
    await graph.ainvoke({"user_id": user.id, "project_id": proj.id, "task_id": 2, "action": "write_next", "scenario": "开一本新书"})
    vols = (await db.scalars(select(Volume).where(Volume.project_id == proj.id))).all()
    assert vols, "应自动创建卷"
    ocs = (await db.scalars(select(OutlineChapter).where(OutlineChapter.volume_id == vols[0].id))).all()
    assert len(ocs) >= 3, "细纲至少 3 章"
    ch = await db.scalar(select(Chapter).where(Chapter.project_id == proj.id, Chapter.chapter_no == 1))
    assert ch is not None and ch.status == "committed"
    events = await collect_events(queue)
    assert any(e.get("stage") == "open-book" for e in events if e["type"] == "stage")


async def test_write_graph_daily_loop_bounded(db):
    """日更循环：连续写，但受 DAILY_CAP 约束有界。"""
    proj, user = await make_project(db)
    queue = asyncio.Queue()
    runtime = GraphRuntime(db=db, user_id=user.id, project_id=proj.id, task_id=3, emit=queue.put_nowait)
    graph = build_write_graph(runtime)
    await graph.ainvoke({"user_id": user.id, "project_id": proj.id, "task_id": 3, "action": "daily", "scenario": "日更"})
    from app.graphs.write import DAILY_CAP

    rows = (await db.scalars(select(Chapter).where(Chapter.project_id == proj.id, Chapter.status == "committed"))).all()
    assert 1 <= len(rows) <= DAILY_CAP
    events = await collect_events(queue)
    assert events  # 有事件（不要求 done——done 由执行器补发）


async def test_api_chapters_next_and_sse(client, db_engine):
    """HTTP 验收：POST /chapters/next → task_id → SSE 事件流含 writing/checkpoint/done。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    r = await client.post("/api/auth/register", json={"username": "w_api", "password": "secret123"})
    assert r.status_code == 201
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = await client.post("/api/projects", json={"slug": "api-book", "title": "接口测试书", "genre": "都市"}, headers=auth)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    # 建细纲（短会话，关闭后再启动后台任务，避免与任务共用单连接）
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sf() as s:
        proj = await s.get(Project, pid)
        vol = Volume(project_id=proj.id, no=1, title="第一卷")
        s.add(vol)
        await s.flush()
        s.add(OutlineChapter(volume_id=vol.id, chapter_no=1, title="开端", beats={"summary": "开局", "target_wordcount": 500}))
        await s.commit()

    r = await client.post(f"/api/projects/{pid}/chapters/next", json={"action": "write_next", "scenario": "帮我写第一章"}, headers=auth)
    assert r.status_code == 200, r.text
    task_id = r.json()["id"]
    assert task_id

    # 轮询任务直到结束（后台任务与测试同 loop）
    status = "pending"
    for _ in range(300):
        r = await client.get(f"/api/tasks/{task_id}", headers=auth)
        assert r.status_code == 200
        status = r.json()["status"]
        if status in ("success", "failed"):
            break
        await asyncio.sleep(0.05)
    assert status == "success", r.json()

    # SSE：事件类型序列
    async with client.stream("GET", f"/api/tasks/{task_id}/events", headers=auth) as resp:
        assert resp.status_code == 200
        kinds = []
        async for line in resp.aiter_lines():
            if line.startswith("data:"):
                ev = json.loads(line[5:].strip())
                kinds.append(ev["type"])
    assert "stage" in kinds and "token" in kinds and "checkpoint" in kinds and kinds[-1] == "done"

    # 提交落库
    r = await client.get(f"/api/projects/{pid}/chapters", headers=auth)
    assert any(c["status"] == "committed" for c in r.json())
    r = await client.get(f"/api/projects/{pid}/tracking", headers=auth)
    assert r.json()["views_consistent"] is True
