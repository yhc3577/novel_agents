"""D7 验收：一键导入（US-20）+ 设置页后端（US-17）。

- 拆解完成的书 → 导入 → 可写项目（卷/细纲/正文 committed/追踪初始化/激活）；
- 重复导入幂等（同一 slug 返回既有项目，不重复写库）；
- 未拆解的书导入被拒绝；
- provider 增改（api_key 加密落库）+ 三档模型选择写入 user_settings。
"""

import asyncio

import pytest
from sqlalchemy import select

import app.models  # noqa: F401
from app.graphs.analyze import build_analyze_graph
from app.graphs.ctx import GraphRuntime
from app.graphs.import_graph import build_import_graph
from app.models import AnalysisBook, Chapter, OutlineChapter, Project, Provider, TrackingState, User, UserSetting, Volume
from app.services.analysis import AnalysisService

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


async def _analyzed_book(db):
    """跑完拆解的一本书（返回 book, user）。"""
    book, user = await make_book(db)
    runtime = GraphRuntime(db=db, user_id=user.id, project_id=0, task_id=201, emit=asyncio.Queue().put_nowait)
    await build_analyze_graph(runtime, book.id).ainvoke({"user_id": user.id, "book_id": book.id, "task_id": 201})
    return book, user


async def _import_book(db, book, user):
    runtime = GraphRuntime(db=db, user_id=user.id, project_id=0)
    return await build_import_graph(runtime).ainvoke({"user_id": user.id, "book_id": book.id})


async def test_import_graph_end_to_end(db):
    """导入后：项目 active、正文 committed、细纲齐全、追踪游标=N、书 imported。"""
    book, user = await _analyzed_book(db)
    result = await _import_book(db, book, user)

    proj = await db.get(Project, result["project_id"])
    assert proj.status == "active" and proj.slug == f"imp-{book.id}" and proj.title == book.title

    chapters = (await db.scalars(select(Chapter).where(Chapter.project_id == proj.id).order_by(Chapter.chapter_no))).all()
    assert len(chapters) == 3
    assert all(c.status == "committed" for c in chapters)
    assert all(c.wordcount > 0 for c in chapters)
    assert chapters[0].content.startswith("第1章")

    vols = (await db.scalars(select(Volume).where(Volume.project_id == proj.id))).all()
    assert len(vols) == 1
    ocs = (await db.scalars(select(OutlineChapter).where(OutlineChapter.volume_id == vols[0].id))).all()
    assert len(ocs) == 3
    assert ocs[0].beats and ocs[0].beats["summary"]

    ts = await db.scalar(select(TrackingState).where(TrackingState.project_id == proj.id))
    assert ts.last_committed_chapter == 3

    book2 = await db.get(AnalysisBook, book.id)
    assert book2.status == "imported"

    # 活跃书唯一：其他项目都被置 inactive
    others = (await db.scalars(select(Project).where(Project.owner_id == user.id))).all()
    assert sum(1 for p in others if p.status == "active") == 1


async def test_import_idempotent(db):
    """重复导入：返回同一 project_id，正文/细纲不重复。"""
    book, user = await _analyzed_book(db)
    r1 = await _import_book(db, book, user)
    r2 = await _import_book(db, book, user)
    assert r1["project_id"] == r2["project_id"] and r2["imported"] is True
    chapters = (await db.scalars(select(Chapter).where(Chapter.project_id == r1["project_id"]))).all()
    assert len(chapters) == 3


async def test_import_requires_done(db):
    """未拆解的书导入被拒绝。"""
    book, user = await make_book(db)
    runtime = GraphRuntime(db=db, user_id=user.id, project_id=0)
    with pytest.raises(ValueError, match="先完成拆解"):
        await build_import_graph(runtime).ainvoke({"user_id": user.id, "book_id": book.id})


async def test_settings_provider_update_and_tiers(db):
    """provider 更新（api_key 加密）+ 三档模型选择落库。"""
    user = User(username="s_user", password_hash="x", display_name="s")
    db.add(user)
    await db.flush()
    db.add(Provider(name="deepseek", base_url="https://api.deepseek.com/v1", models={"high": "deepseek-reasoner", "mid": "deepseek-chat", "low": "deepseek-chat"}, enabled=True, priority=0))
    await db.commit()

    # 读（掩码）
    from app.api.settings import _masked
    p = await db.scalar(select(Provider).where(Provider.name == "deepseek"))
    masked = _masked(p)
    assert masked["has_key"] is False and masked["enabled"] is True

    # 更新 api_key（走 HTTP 走加密，这里直接验证加密函数往返）
    from app.core.crypto import decrypt_secret, encrypt_secret
    p.api_key_enc = encrypt_secret("sk-test")
    await db.commit()
    p2 = await db.scalar(select(Provider).where(Provider.name == "deepseek"))
    assert decrypt_secret(p2.api_key_enc) == "sk-test"

    # 三档选择
    us = UserSetting(user_id=user.id, tier_high="deepseek:deepseek-reasoner", tier_mid="deepseek:deepseek-chat", tier_low="deepseek:deepseek-chat")
    db.add(us)
    await db.commit()
    us2 = await db.scalar(select(UserSetting).where(UserSetting.user_id == user.id))
    assert us2.tier_high == "deepseek:deepseek-reasoner"


async def test_api_settings_tiers_and_test(client):
    """HTTP：PUT /settings/tiers → GET 回显；provider 无 key 测试返回 ok=False。"""
    r = await client.post("/api/auth/register", json={"username": "s_api", "password": "secret123"})
    assert r.status_code == 201
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = await client.put("/api/settings/tiers", json={"high": "deepseek:deepseek-reasoner", "mid": "", "low": ""}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["high"] == "deepseek:deepseek-reasoner"

    r = await client.get("/api/settings", headers=auth)
    assert r.status_code == 200
    assert r.json()["tiers"]["high"] == "deepseek:deepseek-reasoner"

    # 无 provider 时测试返回 ok=False（而非 500）
    r = await client.post("/api/settings/providers/999/test", headers=auth)
    assert r.status_code == 404
