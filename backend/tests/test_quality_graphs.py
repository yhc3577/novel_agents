"""D8 验收：审查 + 去味（US-21/22/23）。

- ReviewGraph：4 reviewer Send 并行合并 findings + 汇总落 chapter_reviews；
- DeslopGraph：扫描→定级（Gate A-G）→改写存 draft + DeslopRun；
- HTTP：跑 review → 看 findings；跑 deslop → 前后对比 + accept 提交。
"""

import asyncio
import json

from sqlalchemy import select

import app.models  # noqa: F401
from app.graphs.ctx import GraphRuntime
from app.graphs.deslop import build_deslop_graph
from app.graphs.review import build_review_graph
from app.graphs.stub_review import grade_findings, stub_deslop, stub_review
from app.models import Chapter, ChapterReview, DeslopRun, Project, User
from app.services.wordcount import measure_text

AI_TEXT = "陈玄不难发现，眼前的局面十分棘手。与此同时，他不得不承认，此事值得注意。然而，他必须做出选择。"
GOOD_TEXT = "陈玄握紧拳，大步冲出门外。门外风雪扑面，他咬牙低喝一声，冲向悬崖边缘。"


async def make_project_with_chapter(db, content=AI_TEXT, no=1):
    user = User(username="q_user", password_hash="x", display_name="q")
    db.add(user)
    await db.flush()
    proj = Project(owner_id=user.id, slug="quality-test", title="审查测试书", genre="玄幻", status="active")
    db.add(proj)
    await db.flush()
    db.add(
        Chapter(
            project_id=proj.id, chapter_no=no, title=f"第{no}章", content=content,
            wordcount=measure_text(content), status="committed", revision=1,
        )
    )
    await db.commit()
    return proj, user


async def collect(queue):
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


def test_grade_findings_bands():
    assert grade_findings([])[0] == "A"
    assert grade_findings([{"severity": "blocking"}])[0] in ("C", "D")
    assert grade_findings([{"severity": "blocking"}] * 3)[0] in ("D", "E", "F")
    assert grade_findings([{"severity": "warning"}] * 20)[0] in ("E", "F")


def test_stub_deslop_removes_ai_phrases():
    out = stub_deslop("陈玄不难发现，与此同时他沉默半晌。……！！")
    assert "不难发现" not in out and "与此同时" not in out and "沉默半晌" not in out
    assert "！！" not in out and "……" in out or "……！" not in out


def test_stub_review_style_finds_patterns():
    findings = stub_review("style", AI_TEXT)
    assert any(f["type"] == "ai_pattern" for f in findings)


async def test_review_graph_demo_send_parallel(db):
    """4 reviewer Send 并行：findings 合并、汇总落库。"""
    proj, user = await make_project_with_chapter(db, AI_TEXT)
    queue = asyncio.Queue()
    runtime = GraphRuntime(db=db, user_id=user.id, project_id=proj.id, task_id=301, emit=queue.put_nowait)
    result = await build_review_graph(runtime).ainvoke(
        {"user_id": user.id, "project_id": proj.id, "chapter_no": 1, "task_id": 301, "mode": "full"}
    )

    findings = result["findings"]
    assert findings
    reviewers = {f["reviewer"] for f in findings}
    assert set(reviewers) <= {"plot", "character", "style", "rhythm"}, reviewers

    row = await db.scalar(select(ChapterReview).where(ChapterReview.project_id == proj.id))
    assert row is not None and 0 <= row.score <= 100 and row.verdict and row.findings

    events = await collect(queue)
    types = [e["type"] for e in events]
    assert "tool" in types and "checkpoint" in types
    # Send 并行：4 个 reviewer 节点都运行（tool 事件齐全），无论是否产出 finding
    tools = [e.get("tool") for e in events if e["type"] == "tool"]
    assert {f"reviewer:{r}" for r in ("plot", "character", "style", "rhythm")} <= set(tools), tools


async def test_review_graph_clean_chapter_no_blocking(db):
    proj, user = await make_project_with_chapter(db, GOOD_TEXT, no=2)
    runtime = GraphRuntime(db=db, user_id=user.id, project_id=proj.id, task_id=302)
    result = await build_review_graph(runtime).ainvoke(
        {"user_id": user.id, "project_id": proj.id, "chapter_no": 2, "task_id": 302, "mode": "lean"}
    )
    # 干净文本不应有 blocking（style 维度 AI 模式为零）
    assert all(f["severity"] != "blocking" for f in result["findings"])


async def test_deslop_graph_demo(db):
    proj, user = await make_project_with_chapter(db, AI_TEXT)
    queue = asyncio.Queue()
    runtime = GraphRuntime(db=db, user_id=user.id, project_id=proj.id, task_id=303, emit=queue.put_nowait)
    result = await build_deslop_graph(runtime).ainvoke(
        {"user_id": user.id, "project_id": proj.id, "chapter_no": 1, "task_id": 303}
    )

    assert result["grade"] and result["rewritten"] != AI_TEXT
    # committed 行不被去味覆盖，前后正文存 deslop_runs
    committed = await db.scalar(
        select(Chapter).where(Chapter.project_id == proj.id, Chapter.status == "committed")
    )
    assert committed is not None and committed.content == AI_TEXT

    run = await db.scalar(select(DeslopRun).where(DeslopRun.project_id == proj.id))
    assert run is not None and run.grade in "ABCDEFG"
    assert run.original == AI_TEXT and "不难发现" not in (run.rewritten or "")

    events = await collect(queue)
    types = [e["type"] for e in events]
    assert "stage" in types and "checkpoint" in types


async def test_api_review_deslop_flow(client, db_engine):
    """HTTP 验收：跑 full 审查→看 findings；跑去味→前后对比→accept 提交。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    r = await client.post("/api/auth/register", json={"username": "q_api", "password": "secret123"})
    assert r.status_code == 201
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = await client.post("/api/projects", json={"slug": "q-api", "title": "接口审查书", "genre": "玄幻"}, headers=auth)
    pid = r.json()["id"]

    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sf() as s:
        s.add(
            Chapter(
                project_id=pid, chapter_no=1, title="第1章", content=AI_TEXT,
                wordcount=measure_text(AI_TEXT), status="committed", revision=1,
            )
        )
        await s.commit()

    # ---- 审查 ----
    r = await client.post(f"/api/projects/{pid}/chapters/1/review", json={"mode": "full"}, headers=auth)
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    for _ in range(300):
        st = (await client.get(f"/api/tasks/{tid}", headers=auth)).json()["status"]
        if st in ("success", "failed"):
            break
        await asyncio.sleep(0.05)
    assert st == "success"

    r = await client.get(f"/api/projects/{pid}/chapters/1/reviews", headers=auth)
    reviews = r.json()
    assert reviews and reviews[0]["findings"]
    reviewers = {f["reviewer"] for f in reviews[0]["findings"]}
    assert set(reviewers) <= {"plot", "character", "style", "rhythm"} and "style" in reviewers

    # ---- 去味 ----
    r = await client.post(f"/api/projects/{pid}/chapters/1/deslop", headers=auth)
    tid = r.json()["id"]
    for _ in range(300):
        st = (await client.get(f"/api/tasks/{tid}", headers=auth)).json()["status"]
        if st in ("success", "failed"):
            break
        await asyncio.sleep(0.05)
    assert st == "success"

    r = await client.get(f"/api/projects/{pid}/chapters/1/deslop", headers=auth)
    d = r.json()
    assert d["ready"] and "不难发现" not in d["rewritten"]
    assert d["new_wordcount"] >= 0 and d["grade"]

    # ---- accept ----
    r = await client.post(f"/api/projects/{pid}/chapters/1/deslop/accept", headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "committed" and r.json()["revision"] == 2
