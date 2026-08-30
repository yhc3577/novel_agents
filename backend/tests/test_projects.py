from httpx import AsyncClient
from sqlalchemy import select

from app.models import Chapter, ChapterReview, Character, Task, UserSetting, Volume
from tests.conftest import register


async def _create(client: AsyncClient, token: str, slug: str, **extra) -> dict:
    r = await client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"slug": slug, "title": "测试之书", **extra},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_list_get(client: AsyncClient):
    tokens = await register(client, "owner1")
    h = {"Authorization": f"Bearer {tokens['access_token']}"}

    p = await _create(client, tokens["access_token"], "my-book", genre="玄幻", platform="起点")
    assert p["status"] == "inactive"
    assert p["slug"] == "my-book"

    lst = (await client.get("/api/projects", headers=h)).json()
    assert len(lst) == 1 and lst[0]["id"] == p["id"]

    got = (await client.get(f"/api/projects/{p['id']}", headers=h)).json()
    assert got["title"] == "测试之书"


async def test_duplicate_slug_409(client: AsyncClient):
    token = (await register(client, "dup1"))["access_token"]
    await _create(client, token, "dup-book")
    r = await client.post(
        "/api/projects", headers={"Authorization": f"Bearer {token}"}, json={"slug": "dup-book", "title": "另一本"}
    )
    assert r.status_code == 409


async def test_owner_isolation(client: AsyncClient):
    """租户隔离：A 创建的项目，B 列表看不到、详情 404、不能激活。"""
    t_a = (await register(client, "alice_a"))["access_token"]
    t_b = (await register(client, "bob_b"))["access_token"]

    p = await _create(client, t_a, "secret-book")
    h_b = {"Authorization": f"Bearer {t_b}"}

    lst = (await client.get("/api/projects", headers=h_b)).json()
    assert all(x["id"] != p["id"] for x in lst)

    r = await client.get(f"/api/projects/{p['id']}", headers=h_b)
    assert r.status_code == 404

    r = await client.post(f"/api/projects/{p['id']}/activate", headers=h_b)
    assert r.status_code == 404


async def test_activate_switches_active_book(client: AsyncClient):
    token = (await register(client, "act1"))["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    p1 = await _create(client, token, "book-one")
    p2 = await _create(client, token, "book-two")

    r = await client.post(f"/api/projects/{p2['id']}/activate", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "active"

    # p1 被切回 inactive
    r1 = (await client.get(f"/api/projects/{p1['id']}", headers=h)).json()
    assert r1["status"] == "inactive"


async def test_update_project(client: AsyncClient):
    token = (await register(client, "upd1"))["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    p = await _create(client, token, "upd-book")
    r = await client.patch(
        f"/api/projects/{p['id']}", headers=h, json={"title": "改名", "genre": "科幻"}
    )
    assert r.status_code == 200
    assert r.json()["title"] == "改名"
    assert r.json()["genre"] == "科幻"


async def test_projects_require_auth(client: AsyncClient):
    r = await client.get("/api/projects")
    assert r.status_code == 401


async def test_delete_project_cascades(client: AsyncClient, db):
    """删除项目应整树清理附属数据（章节/追踪/审查/任务等），且无主用户数据不动。"""
    token = (await register(client, "del1"))["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    p = await _create(client, token, "del-book")

    # 造一层附属数据：章节 + 审查 + 人物 + 任务 + 用户默认项目
    me = (await client.get("/api/auth/me", headers=h)).json()
    db.add_all([
        Volume(project_id=p["id"], no=1, title="卷1"),
        Chapter(project_id=p["id"], chapter_no=1, title="第一章", content="正文", status="committed"),
        Character(project_id=p["id"], name="主角", profile={"性格": "坚韧"}),
        ChapterReview(project_id=p["id"], chapter_no=1, mode="full", score=8, verdict="pass", findings=[], summary="好"),
        Task(owner_id=me["id"], project_id=p["id"], type="write_chapter", status="success", payload={"a": 1}),
        UserSetting(user_id=me["id"], default_project_id=p["id"]),
    ])
    await db.commit()

    r = await client.delete(f"/api/projects/{p['id']}", headers=h)
    assert r.status_code == 200

    # 项目与其附属行全部消失
    assert (await client.get(f"/api/projects/{p['id']}", headers=h)).status_code == 404
    for model in (Chapter, ChapterReview, Character, Task, Volume):
        assert (await db.scalar(select(model).where(model.project_id == p["id"]))) is None
    # 用户默认项目引用被摘除（用户设置本身保留）
    us = (await db.scalar(select(UserSetting).where(UserSetting.user_id == me["id"])))
    assert us is not None and us.default_project_id is None


async def test_delete_project_owner_isolation(client: AsyncClient):
    """越权删除 404；重复删除 404。"""
    t_a = (await register(client, "del_a"))["access_token"]
    t_b = (await register(client, "del_b"))["access_token"]
    p = await _create(client, t_a, "del-secret")

    r = await client.delete(f"/api/projects/{p['id']}", headers={"Authorization": f"Bearer {t_b}"})
    assert r.status_code == 404
    r = await client.delete(f"/api/projects/{p['id']}", headers={"Authorization": f"Bearer {t_a}"})
    assert r.status_code == 200
    r = await client.delete(f"/api/projects/{p['id']}", headers={"Authorization": f"Bearer {t_a}"})
    assert r.status_code == 404
