"""D13+ 验收：开书流水线（世界观 → 大纲 → 细纲）+ 分阶段重试 + confirm 交互模式。

验收点：
- GET /projects/{pid}/outline：空项目 has_outline=false；开书后 卷→章→细纲 视图正确；
- POST /projects/{pid}/open-book：auto 模式后台生成 3 章，SSE 见 worldview/outline/beats + done；
- confirm 模式：每阶段发 stage_draft 暂停，draft-confirm 确认后继续，修改内容入库；
- stage=outline/beats 重试：保留前置产物，重生成该阶段及之后；
- force=true：全清重新生成；已有大纲且非 force：静默跳过；
- 越权访问他人项目大纲/发起开书 → 404。
"""

import asyncio
import json

from sqlalchemy import select

import app.models  # noqa: F401
from app.graphs.ctx import GraphRuntime
from app.models import OutlineChapter, Project, Setting, User, Volume
from app.services.outline import generate_outline


async def _register(client, username: str) -> dict:
    r = await client.post("/api/auth/register", json={"username": username, "password": "secret123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _wait_success(client, auth: dict, task_id: int, timeout: int = 300) -> str:
    for _ in range(timeout):
        r = await client.get(f"/api/tasks/{task_id}", headers=auth)
        assert r.status_code == 200, r.text
        st = r.json()["status"]
        if st in ("success", "failed", "cancelled"):
            return st
        await asyncio.sleep(0.02)
    raise AssertionError(f"任务 {task_id} 等待超时")


async def test_outline_empty_project(client):
    auth = await _register(client, "ob_empty")
    r = await client.post("/api/projects", json={"slug": "ob-empty", "title": "空项目", "genre": "玄幻"}, headers=auth)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    r = await client.get(f"/api/projects/{pid}/outline", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["has_outline"] is False
    assert body["volumes"] == []


async def _fresh_session(db_engine):
    """任务完成后用独立 session 断言（避免与后台任务共享 StaticPool 连接冲突）。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    return sf


async def test_open_book_generates_outline(client, db_engine):
    auth = await _register(client, "ob_gen")
    r = await client.post("/api/projects", json={"slug": "ob-gen", "title": "开书项目", "genre": "玄幻"}, headers=auth)
    pid = r.json()["id"]

    # 开书前 GET：无大纲
    r = await client.get(f"/api/projects/{pid}/outline", headers=auth)
    assert r.json()["has_outline"] is False

    r = await client.post(f"/api/projects/{pid}/open-book", json={"scenario": "都市修仙"}, headers=auth)
    assert r.status_code == 200, r.text
    task_id = r.json()["id"]
    assert task_id
    assert await _wait_success(client, auth, task_id) == "success"

    # SSE 事件流：三阶段按序出现、以 done 收尾
    async with client.stream("GET", f"/api/tasks/{task_id}/events", headers=auth) as resp:
        assert resp.status_code == 200
        stages, kinds = [], []
        async for line in resp.aiter_lines():
            if line.startswith("data:"):
                ev = json.loads(line[5:].strip())
                kinds.append(ev["type"])
                if ev["type"] == "stage":
                    stages.append(ev["stage"])
    assert stages == ["worldview", "outline", "beats"]
    assert kinds[-1] == "done"

    # GET 大纲视图
    r = await client.get(f"/api/projects/{pid}/outline", headers=auth)
    body = r.json()
    assert body["has_outline"] is True
    assert len(body["volumes"]) == 1
    vol = body["volumes"][0]
    assert vol["no"] == 1 and vol["title"]
    assert len(vol["chapters"]) >= 3
    ch = vol["chapters"][0]
    assert ch["chapter_no"] == 1 and ch["title"]
    assert ch["contract_status"] == "valid"
    # beats 归一化：summary + target_wordcount + points（细纲情节点非空）
    assert ch["beats"]["summary"]
    assert ch["beats"]["target_wordcount"] == 2000
    assert len(ch["beats"]["points"]) > 0

    # 世界观/设定已落库（独立 session，任务已结束）
    sf = await _fresh_session(db_engine)
    async with sf() as s:
        rows = (await s.scalars(select(Setting).where(Setting.project_id == pid))).all()
    assert len(rows) >= 3
    assert any(r.kind == "世界观" and r.content for r in rows)


async def test_outline_owner_isolation(client):
    auth_a = await _register(client, "ob_owner_a")
    auth_b = await _register(client, "ob_owner_b")
    r = await client.post("/api/projects", json={"slug": "ob-priv", "title": "私有项目", "genre": "玄幻"}, headers=auth_a)
    pid = r.json()["id"]
    r = await client.get(f"/api/projects/{pid}/outline", headers=auth_b)
    assert r.status_code == 404
    r = await client.post(f"/api/projects/{pid}/open-book", json={}, headers=auth_b)
    assert r.status_code == 404


async def _gen(db, runtime_id: int):
    user = User(username=f"ob_svc_{runtime_id}", password_hash="x", display_name="x")
    db.add(user)
    await db.flush()
    proj = Project(owner_id=user.id, slug=f"ob-svc-{runtime_id}", title="覆盖项目", genre="玄幻")
    db.add(proj)
    await db.commit()
    queue = asyncio.Queue()
    runtime = GraphRuntime(db=db, user_id=user.id, project_id=proj.id, task_id=runtime_id, emit=queue.put_nowait)
    return proj, runtime, queue


async def test_generate_outline_force_replaces(db):
    proj, runtime, _ = await _gen(db, 11)
    pid = proj.id
    assert await generate_outline(db, runtime, project_id=pid, scenario="第一版") == 3

    vols = (await db.scalars(select(Volume).where(Volume.project_id == pid))).all()
    assert len(vols) == 1
    oc = await db.scalar(
        select(OutlineChapter).where(OutlineChapter.volume_id == vols[0].id, OutlineChapter.chapter_no == 1)
    )
    oc.title = "被篡改的标题"
    await db.commit()

    # force 覆盖：卷数不变，章节被 stub 确定性内容替换，设定一并重建
    assert await generate_outline(db, runtime, project_id=pid, scenario="第二版", force=True) == 3
    vols2 = (await db.scalars(select(Volume).where(Volume.project_id == pid))).all()
    assert len(vols2) == 1
    ocs = (
        await db.scalars(
            select(OutlineChapter).where(OutlineChapter.volume_id == vols2[0].id).order_by(OutlineChapter.chapter_no)
        )
    ).all()
    assert len(ocs) == 3
    assert ocs[0].title == "苏醒"  # stub 第一卷第一章确定性标题
    settings = (await db.scalars(select(Setting).where(Setting.project_id == pid))).all()
    assert len(settings) >= 3


async def test_generate_outline_skip_when_exists(db):
    proj, runtime, queue = await _gen(db, 12)
    pid = proj.id
    assert await generate_outline(db, runtime, project_id=pid, scenario="初版") == 3
    while not queue.empty():
        queue.get_nowait()

    # 已有大纲且非 force：静默跳过，返回现有章数、不落新卷、不发事件
    n = await generate_outline(db, runtime, project_id=pid, scenario="再来一遍")
    assert n == 3
    vols = (await db.scalars(select(Volume).where(Volume.project_id == pid))).all()
    assert len(vols) == 1
    assert queue.empty()


async def test_generate_outline_retry_outline_keeps_settings(db):
    proj, runtime, _ = await _gen(db, 21)
    pid = proj.id
    await generate_outline(db, runtime, project_id=pid, scenario="初版")

    settings = (await db.scalars(select(Setting).where(Setting.project_id == pid))).all()
    assert settings
    vols = (await db.scalars(select(Volume).where(Volume.project_id == pid))).all()
    vols[0].title = "被改的卷名"
    await db.commit()

    # 重试 outline：设定保留，卷/章重生成（stub 确定性标题恢复）
    await generate_outline(db, runtime, project_id=pid, stage="outline")
    vols2 = (await db.scalars(select(Volume).where(Volume.project_id == pid))).all()
    assert len(vols2) == 1 and vols2[0].title == "第一卷·风起"
    settings2 = (await db.scalars(select(Setting).where(Setting.project_id == pid))).all()
    assert len(settings2) == len(settings)
    assert all(s.id in {x.id for x in settings} for s in settings2)


async def test_generate_outline_retry_beats_keeps_volume(db):
    proj, runtime, _ = await _gen(db, 22)
    pid = proj.id
    await generate_outline(db, runtime, project_id=pid, scenario="初版")

    vols = (await db.scalars(select(Volume).where(Volume.project_id == pid))).all()
    vol_id = vols[0].id
    oc = await db.scalar(
        select(OutlineChapter).where(OutlineChapter.volume_id == vol_id, OutlineChapter.chapter_no == 1)
    )
    oc.beats = {"summary": "被改的摘要", "points": []}
    await db.commit()

    # 重试 beats：卷保留，细纲重生成（stub 恢复）
    await generate_outline(db, runtime, project_id=pid, stage="beats")
    vols2 = (await db.scalars(select(Volume).where(Volume.project_id == pid))).all()
    assert [v.id for v in vols2] == [vol_id]
    oc2 = await db.scalar(
        select(OutlineChapter).where(OutlineChapter.volume_id == vol_id, OutlineChapter.chapter_no == 1)
    )
    assert oc2.beats["summary"]
    assert len(oc2.beats["points"]) > 0


async def test_open_book_confirm_mode_interactive(client, db_engine):
    """confirm 模式：每阶段发 stage_draft 暂停，draft-confirm 确认后继续，修改内容入库。

    说明：httpx ASGITransport 会整体缓冲响应体，SSE 流未结束前不会把事件交给测试，
    因此不能边读 SSE 边 POST（会死锁）。这里改为直接从任务事件队列驱动交互
    （SSE 端点的序列化已由 test_open_book_generates_outline 覆盖）。
    """
    from app.services.task_service import TaskService

    auth = await _register(client, "ob_confirm")
    r = await client.post("/api/projects", json={"slug": "ob-confirm", "title": "确认项目", "genre": "玄幻"}, headers=auth)
    pid = r.json()["id"]

    r = await client.post(f"/api/projects/{pid}/open-book", json={"mode": "confirm"}, headers=auth)
    assert r.status_code == 200, r.text
    task_id = r.json()["id"]

    handle = TaskService().registry_get(task_id)
    assert handle is not None

    stages_seen = []
    while True:
        payload = await asyncio.wait_for(handle.queue.get(), timeout=30)
        t = payload["type"]
        if t == "stage_draft":
            stages_seen.append(payload["stage"])
            content = payload["content"]
            if payload["stage"] == "worldview":
                # 修改世界观后再入库
                content = "## 世界观\n天玄大陆，改过后的世界观。\n## 人设\n陈玄，改过的人设。"
            r = await client.post(
                f"/api/tasks/{task_id}/draft-confirm",
                json={"action": "confirm", "content": content},
                headers=auth,
            )
            assert r.status_code == 200, r.text
        if t == "error":
            raise AssertionError(f"开书任务失败: {payload.get('error')}")
        if t == "done":
            break
    assert stages_seen == ["worldview", "outline", "beats"]

    # 世界观确认内容已入库（修改生效；独立 session）
    sf = await _fresh_session(db_engine)
    async with sf() as s:
        rows = (await s.scalars(select(Setting).where(Setting.project_id == pid))).all()
        contents = {r.kind: r.content for r in rows}
    assert "改过后的世界观" in contents.get("世界观", "")
    # 大纲/细纲正常生成
    r = await client.get(f"/api/projects/{pid}/outline", headers=auth)
    body = r.json()
    assert body["has_outline"] is True
    ch = body["volumes"][0]["chapters"][0]
    assert ch["beats"]["summary"]
    assert len(ch["beats"]["points"]) > 0
