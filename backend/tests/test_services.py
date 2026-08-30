"""D3 验收：服务层核心（US-08,09,10,11）。

关键验收：
- 章节提交事务原子性——一次 commit 同时更新 chapters / 角色 / 伏笔 / 时间线、
  重建 chapter_records + context_views、revision+1；
- 追踪事务 JSON 先过契约后校验再入库（坏契约零写入）；
- 字数非对称收口；
- 质量门禁返回 findings。
"""

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

import app.models  # noqa: F401
from app.models import (
    Chapter,
    ChapterRecord,
    Character,
    ContextView,
    Foreshadowing,
    OutlineChapter,
    Project,
    TimelineEvent,
    TrackingState,
    User,
    Volume,
)
from app.schemas.tracking import TrackingTx
from app.services.chapter import ChapterService
from app.services.context import ContextService, MemoryService
from app.services.quality import QualityBlockError, QualityService
from app.services.tracking import TrackingConflict, TrackingService
from app.services.wordcount import WordcountService


# ---- fixtures ----

@pytest.fixture
async def project(db):
    user = User(username="svc_user", password_hash="x", display_name="svc")
    db.add(user)
    await db.flush()
    proj = Project(owner_id=user.id, slug="demo-book", title="仙路初开", genre="玄幻", status="active")
    db.add(proj)
    await db.flush()
    vol = Volume(project_id=proj.id, no=1, title="第一卷")
    db.add(vol)
    await db.flush()
    oc = OutlineChapter(
        volume_id=vol.id,
        chapter_no=1,
        title="初入仙门",
        beats={"summary": "主角觉醒", "target_wordcount": 1000},
    )
    db.add(oc)
    await db.commit()
    proj.id = proj.id
    return proj


def tx(**over) -> dict:
    base = {
        "chapter_no": 1,
        "characters": [{"name": "陈玄", "kind": "主角", "profile": {"出身": "猎户"}}],
        "foreshadowing": [{"content": "神秘玉佩异动"}],
        "timeline": [{"content": "陈玄自昏迷中醒来", "author_only": False}],
    }
    base.update(over)
    return base


# ---- TrackingService ----

async def test_tracking_init_and_check(db, project):
    svc = TrackingService(db)
    rev = await svc.init(project.id, {"seed": "开书快照"})
    assert rev == 1
    st = await db.scalar(select(TrackingState).where(TrackingState.project_id == project.id))
    assert st.state_revision == 1

    info = await svc.check(project.id)
    assert info["last_committed_chapter"] == 0
    assert info["state_revision"] == 1
    assert info["views_consistent"] is False


async def test_tracking_commit_single_transaction(db, project):
    """一次 commit：角色/伏笔/时间线联动 + 派生视图重建 + revision+1。"""
    svc = TrackingService(db)
    await svc.init(project.id, {})
    rev = await svc.commit(project.id, tx())
    assert rev == 2

    # 角色
    c = await db.scalar(select(Character).where(Character.project_id == project.id, Character.name == "陈玄"))
    assert c is not None and c.kind == "主角" and c.profile["出身"] == "猎户"
    # 伏笔
    f = await db.scalar(select(Foreshadowing).where(Foreshadowing.project_id == project.id))
    assert f is not None and f.planted_chapter == 1 and f.status == "planted"
    # 时间线
    t = await db.scalar(select(TimelineEvent).where(TimelineEvent.project_id == project.id))
    assert t is not None and t.chapter_no == 1 and t.author_only is False
    # 版本
    st = await db.scalar(select(TrackingState).where(TrackingState.project_id == project.id))
    assert st.state_revision == 2 and st.last_committed_chapter == 1
    # 派生视图
    rec = await db.scalar(select(ChapterRecord).where(ChapterRecord.project_id == project.id))
    assert rec is not None and rec.chapter_no == 1 and rec.characters and rec.events and rec.foreshadowing
    view = await db.scalar(select(ContextView).where(ContextView.project_id == project.id))
    assert view is not None and view.revision == 2 and "大纲" in view.content
    # 一致性
    assert (await svc.check(project.id))["views_consistent"] is True


async def test_tracking_contract_first_no_partial_write(db, project):
    """契约先于入库：坏契约 → 零写入（角色/伏笔/时间线/revision 均不变）。"""
    svc = TrackingService(db)
    await svc.init(project.id, {})
    bad = tx(characters=[{"name": "", "kind": "主角"}])  # name 违反 min_length
    with pytest.raises(ValidationError):
        TrackingTx.model_validate(bad)
    with pytest.raises(ValidationError):
        await svc.commit(project.id, bad)
    assert (await db.scalar(select(func.count()).select_from(Character))) == 0
    assert (await db.scalar(select(func.count()).select_from(Foreshadowing))) == 0
    assert (await db.scalar(select(func.count()).select_from(TimelineEvent))) == 0
    st = await db.scalar(select(TrackingState).where(TrackingState.project_id == project.id))
    assert st.state_revision == 1  # 未推进


async def test_tracking_expected_revision_guard(db, project):
    """版本守卫：expected_revision 不匹配 → TrackingConflict 且无写库。"""
    pid = project.id
    svc = TrackingService(db)
    await svc.init(pid, {})
    await svc.commit(pid, tx())
    with pytest.raises(TrackingConflict):
        await svc.commit(pid, tx(), expected_revision=1)  # 实际已=2
    st = await db.scalar(select(TrackingState).where(TrackingState.project_id == pid))
    assert st.state_revision == 2


async def test_tracking_character_upsert_and_resolve(db, project):
    """同名角色修订 + 引爆已有伏笔。"""
    pid = project.id
    svc = TrackingService(db)
    await svc.init(pid, {})
    await svc.commit(pid, tx())
    f = await db.scalar(select(Foreshadowing).where(Foreshadowing.project_id == pid))
    rev = await svc.commit(
        pid,
        tx(
            chapter_no=2,
            characters=[{"name": "陈玄", "revise": True, "profile": {"出身": "猎户", "修为": "练气一层"}}],
            foreshadowing=[{"content": "引爆玉佩", "resolve_id": f.id}],
            timeline=[{"content": "玉佩突然亮起", "chapter_no": 2, "author_only": True}],
        ),
    )
    assert rev == 3
    c = await db.scalar(select(Character).where(Character.project_id == pid, Character.name == "陈玄"))
    assert c.profile["修为"] == "练气一层"
    f2 = await db.get(Foreshadowing, f.id)
    assert f2.status == "resolved" and f2.resolved_chapter == 2


# ---- ChapterService ----

async def test_chapter_draft_check_commit_atomic(db, project):
    """章节原子提交：chapters / 追踪 / 派生视图 / revision+1 一步到位。"""
    await TrackingService(db).init(project.id, {})  # revision 从 1 起
    svc = ChapterService(db)
    ch = await svc.draft(project.id, 1, "陈玄自昏迷中醒来，眼前是一片荒山。一块玉佩静静躺在掌心。" * 20)
    assert ch.status == "draft"
    assert ch.wordcount > 0

    assert await svc.check(project.id, 1) in ("in_range", "under", "over")  # target=1000

    committed = await svc.commit(project.id, 1, tx())
    assert committed.status == "committed"
    assert committed.revision == 1

    st = await db.scalar(select(TrackingState).where(TrackingState.project_id == project.id))
    assert st.state_revision == 2
    view = await db.scalar(select(ContextView).where(ContextView.project_id == project.id))
    assert view.revision == 2 and "角色" in view.content


async def test_chapter_commit_blocked_by_quality(db, project):
    """质量门禁 blocking → 提交被拒，章节保持 draft、追踪无写入。"""
    svc = ChapterService(db)
    await svc.draft(project.id, 1, "不难发现，陈玄对此并不意外。")
    with pytest.raises(QualityBlockError):
        await svc.commit(project.id, 1, tx(), fail_on="blocking")
    ch = await db.scalar(select(Chapter).where(Chapter.project_id == project.id))
    assert ch.status == "draft"
    assert (await db.scalar(select(func.count()).select_from(TrackingState))) == 0


# ---- WordcountService ----

async def test_wordcount_measure_zh_hybrid():
    assert WordcountService.measure_text("你好 world 你好") == 5  # 4 中文字 + 1 英文词
    assert WordcountService.measure_text("") == 0
    assert WordcountService.measure_text("123 abc") == 2


def test_wordcount_asymmetric_constriction():
    """非对称收口：under 更严（<0.95×target），over 更松（>1.2×target）。"""
    target = 1000
    assert WordcountService.evaluate_actual(940, target) == "under"
    assert WordcountService.evaluate_actual(960, target) == "in_range"
    assert WordcountService.evaluate_actual(1000, target) == "in_range"
    assert WordcountService.evaluate_actual(1190, target) == "in_range"
    assert WordcountService.evaluate_actual(1210, target) == "over"


# ---- QualityService ----

async def test_quality_findings_and_blocking(db, project):
    q = QualityService(db)
    ch = await db.scalar(select(Chapter).where(Chapter.project_id == project.id))
    if ch is None:
        ch = await ChapterService(db).draft(project.id, 1, "不难发现，陈玄不禁沉默半晌。！！")
    findings = await q.ai_patterns(ch.id, fail_on="none")
    assert any(f.type == "ai_pattern" for f in findings)

    report = await q.full_gate(ch.id, fail_on="none")
    assert report.blocking  # 半角/堆叠标点 + AI 句式均 blocking
    assert await q.banned_words(ch.id) == []

    with pytest.raises(QualityBlockError):
        await q.full_gate(ch.id, fail_on="blocking")


async def test_quality_outline_contract(db, project):
    q = QualityService(db)
    res = await q.outline_contract(project.id)
    assert res["valid"] is True  # 细纲有 beats，未提交章节
    # 提交一章但大纲被清空 beats → 报错
    ch = await db.scalar(select(Chapter).where(Chapter.project_id == project.id))
    if ch is not None:
        ch.status = "committed"
        await db.flush()
    oc = await db.scalar(select(OutlineChapter).where(OutlineChapter.volume_id.is_not(None)))
    if oc:
        oc.beats = None
        await db.flush()
    res2 = await q.outline_contract(project.id)
    assert res2["valid"] is False and res2["errors"]


# ---- ContextService ----

async def test_context_view_7_cols_under_12kb(db, project):
    ctx = ContextService(db)
    # 先跑一次 commit 造数据
    await TrackingService(db).init(project.id, {})
    await TrackingService(db).commit(project.id, tx())
    view = await ctx.build_context_view(project.id)
    for label in ("大纲", "最近章节", "角色", "伏笔", "时间线", "设定", "作者记忆"):
        assert label in view
    assert len(view.encode("utf-8")) <= 12 * 1024

    pack = await ctx.recall_pack(project.id)
    assert pack["topic_card"].startswith("仙路初开")
    assert "陈玄" in pack["context_view"]


async def test_memory_service_kb_limit(db, project):
    mem = MemoryService(db)
    await mem.record(project.owner_id, "preference", "偏好简洁描写", scope="style")
    await mem.record(project.owner_id, "preference", "偏好" * 300, scope="style")  # 约 5.4KB，超出
    rows = await mem.query(project.owner_id, ["preference"], limit_kb=1.0)
    # 超限条目被跳过，小条目保留
    assert [r.content for r in rows] == ["偏好简洁描写"]
