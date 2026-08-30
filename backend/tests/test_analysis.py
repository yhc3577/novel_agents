"""D6 验收：拆文后端（US-18）。

验收点：
- 上传整书文本 → 跑完拆解 → analysis_aggregates 各 kind（9 种）落库；
- map 并行逐章提取（stage1）产出每章 summary+beats；
- 中断/失败后重跑：从 analysis_progress 续——done 阶段跳过，失败阶段重跑；
- API：POST /analysis/books → POST /analyze → SSE/task → GET 快照含全部分维聚合。
"""

import asyncio
import json

from sqlalchemy import select

import app.models  # noqa: F401
from app.graphs.analyze import build_analyze_graph
from app.graphs.ctx import GraphRuntime
from app.graphs.stub_analysis import extract_chapter, split_chapters
from app.models import AnalysisAggregate, AnalysisBook, AnalysisChapter, AnalysisProgress, User
from app.services.analysis import ALL_KINDS, AnalysisService

SAMPLE_TEXT = """第1章 苏醒
清晨，陈玄从昏迷中醒来，发现自己躺在一片荒山。他记得自己被人暗算，坠入悬崖。一块温润的玉佩静静躺在掌心。他猛地坐起，心中翻涌着不甘与怒火。
第2章 试炼
陈玄沿着山道艰难前行，遭遇一头巨兽。他咬牙迎战，玉佩突然发出光芒，一股力量涌入四肢。他一掌击出，巨兽轰然倒地。他怔在原地，没想到这玉佩藏着机缘。
第3章 抉择
山下小镇，陈玄用打到的兽皮换了盘缠。茶馆里，他听到有人提及青云宗与一件惊天秘闻。他心中一动：这或许是改变命运的契机。夜半，一个蒙面人敲响他的房门。
"""


async def make_book(db, title="测试书", text=SAMPLE_TEXT):
    user = User(username="a_user", password_hash="x", display_name="a")
    db.add(user)
    await db.flush()
    book = await AnalysisService(db).create_book(user.id, title=title, genre="玄幻", source_text=text)
    return book, user


def test_split_chapters():
    bounds = split_chapters(SAMPLE_TEXT)
    assert len(bounds) == 3
    assert [b["no"] for b in bounds] == [1, 2, 3]
    assert SAMPLE_TEXT[bounds[0]["start"] : bounds[0]["end"]].startswith("第1章")
    assert "清晨" in SAMPLE_TEXT[bounds[0]["start"] : bounds[0]["end"]]
    assert bounds[2]["end"] == len(SAMPLE_TEXT)


def test_stub_extract_chapter():
    out = extract_chapter(SAMPLE_TEXT, 1)
    assert out["summary"] and len(out["beats"]) >= 1 and isinstance(out["hooks"], list)


async def test_analyze_graph_end_to_end(db):
    """整书拆解端到端：9 个 kind 聚合落库 + 章节提取 + 进度全 done。"""
    book, user = await make_book(db)
    queue = asyncio.Queue()
    runtime = GraphRuntime(db=db, user_id=user.id, project_id=0, task_id=101, emit=queue.put_nowait)
    graph = build_analyze_graph(runtime, book.id)
    await graph.ainvoke({"user_id": user.id, "book_id": book.id, "task_id": 101})

    # 聚合 9 种全部落库
    aggs = (await db.scalars(select(AnalysisAggregate).where(AnalysisAggregate.book_id == book.id))).all()
    kinds = {a.kind for a in aggs}
    assert set(ALL_KINDS) <= kinds, f"缺聚合: {set(ALL_KINDS) - kinds}"

    # 章节提取
    chapters = (await db.scalars(select(AnalysisChapter).where(AnalysisChapter.book_id == book.id))).all()
    assert len(chapters) == 3
    assert all(c.summary and c.beats for c in chapters)

    # 进度
    stages = (await db.scalars(select(AnalysisProgress).where(AnalysisProgress.book_id == book.id))).all()
    assert {s.stage: s.status for s in stages} == {f"stage{i}": "done" for i in range(7)}

    # 书状态
    book2 = await db.get(AnalysisBook, book.id)
    assert book2.status == "done"

    # SSE 事件含 stage/tool/checkpoint（图直接调用不产 done）
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    types = [e["type"] for e in events]
    assert "stage" in types and "checkpoint" in types


async def test_analyze_graph_resume_skips_done_stages(db):
    """断点恢复：stage1 已完成则重跑跳过（章节摘要不被覆盖）；失败阶段重跑。"""
    book, user = await make_book(db)
    queue = asyncio.Queue()
    runtime = GraphRuntime(db=db, user_id=user.id, project_id=0, task_id=102, emit=queue.put_nowait)
    graph = build_analyze_graph(runtime, book.id)
    await graph.ainvoke({"user_id": user.id, "book_id": book.id, "task_id": 102})

    # 人为制造断点：stage1 已完成（章节摘要钉住）；stage3 标记失败，emotion 聚合污染
    ch = await db.scalar(select(AnalysisChapter).where(AnalysisChapter.book_id == book.id, AnalysisChapter.chapter_no == 1))
    ch.summary = "SENTINEL"
    await AnalysisService(db).mark_stage(book.id, "stage3", status="failed")
    emo = await db.scalar(select(AnalysisAggregate).where(AnalysisAggregate.book_id == book.id, AnalysisAggregate.kind == "emotion"))
    emo.content = "GARBAGE"
    await db.commit()

    # 重跑
    await graph.ainvoke({"user_id": user.id, "book_id": book.id, "task_id": 102})

    # stage1 跳过：摘要仍为 SENTINEL
    ch2 = await db.scalar(select(AnalysisChapter).where(AnalysisChapter.book_id == book.id, AnalysisChapter.chapter_no == 1))
    assert ch2.summary == "SENTINEL", "stage1 不应重跑"

    # stage3 重跑：emotion 聚合被确定性内容覆盖（非 GARBAGE）
    emo2 = await db.scalar(select(AnalysisAggregate).where(AnalysisAggregate.book_id == book.id, AnalysisAggregate.kind == "emotion"))
    assert emo2.content and emo2.content != "GARBAGE"

    # 最终进度全 done
    stages = (await db.scalars(select(AnalysisProgress).where(AnalysisProgress.book_id == book.id))).all()
    assert all(s.status == "done" for s in stages)


async def test_api_upload_analyze_and_snapshot(client):
    """HTTP 验收：上传文本 → 发起拆文 → 任务 success → 快照含 9 种聚合。"""
    r = await client.post("/api/auth/register", json={"username": "a_api", "password": "secret123"})
    assert r.status_code == 201
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = await client.post(
        "/api/analysis/books",
        json={"title": "接口拆文书", "genre": "玄幻", "source_text": SAMPLE_TEXT},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    book_id = r.json()["id"]

    r = await client.post(f"/api/analysis/books/{book_id}/analyze", headers=auth)
    assert r.status_code == 200, r.text
    task_id = r.json()["id"]

    status = "pending"
    for _ in range(300):
        r = await client.get(f"/api/tasks/{task_id}", headers=auth)
        assert r.status_code == 200
        status = r.json()["status"]
        if status in ("success", "failed"):
            break
        await asyncio.sleep(0.05)
    assert status == "success", r.json()

    # SSE 事件流
    async with client.stream("GET", f"/api/tasks/{task_id}/events", headers=auth) as resp:
        assert resp.status_code == 200
        kinds = []
        async for line in resp.aiter_lines():
            if line.startswith("data:"):
                ev = json.loads(line[5:].strip())
                kinds.append(ev["type"])
    assert kinds[-1] == "done"

    # 快照
    r = await client.get(f"/api/analysis/books/{book_id}", headers=auth)
    snap = r.json()
    assert snap["status"] == "done"
    assert set(ALL_KINDS) <= set(snap["aggregates"].keys())
    assert len(snap["chapters"]) == 3
    assert all(p == "done" for p in snap["progress"].values())

    # 报告
    r = await client.get(f"/api/analysis/books/{book_id}/report", headers=auth)
    assert r.status_code == 200 and r.json()["report"]
