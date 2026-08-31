"""D13 验收：开书可视化——大纲读取 + 开书任务（后台生成 + 覆盖重生成 + 越权隔离）。

验收点：
- GET /projects/{pid}/outline：空项目 has_outline=false；开书后 卷→章→细纲 视图正确；
- POST /projects/{pid}/open-book：返回 task_id，后台 demo 模式生成 3 章大纲，SSE 见 stage/done；
- force=true：删旧大纲重新生成，卷数不变、章节被覆盖（stub 确定性标题验证）；
- 已有大纲且非 force：静默跳过（不落新卷、不发事件）；
- 越权访问他人项目大纲/发起开书 → 404。
"""

import asyncio
import json

from sqlalchemy import select

import app.models  # noqa: F401
from app.graphs.ctx import GraphRuntime
from app.models import OutlineChapter, Project, User, Volume
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


async def test_open_book_generates_outline(client):
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

    # SSE 事件流：stage 出现、以 done 收尾（任务可能已完成 → 补发 done）
    async with client.stream("GET", f"/api/tasks/{task_id}/events", headers=auth) as resp:
        assert resp.status_code == 200
        kinds = []
        async for line in resp.aiter_lines():
            if line.startswith("data:"):
                ev = json.loads(line[5:].strip())
                kinds.append(ev["type"])
    assert "stage" in kinds
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
    # beats 归一化：开书写入形状 → summary + target_wordcount + points
    assert ch["beats"]["summary"]
    assert ch["beats"]["target_wordcount"] == 2000
    assert ch["beats"]["points"] == []


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

    # force 覆盖：卷数不变，章节被 stub 确定性内容替换
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
