from httpx import AsyncClient


async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_register_login_me(client: AsyncClient):
    tokens = await _register(client, "alice", email="a@example.com")
    assert tokens["access_token"] and tokens["refresh_token"]

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    r = await client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    me = r.json()
    assert me["username"] == "alice"
    assert me["email"] == "a@example.com"

    r = await client.post("/api/auth/login", json={"username": "alice", "password": "secret123"})
    assert r.status_code == 200

    r = await client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 401


async def test_duplicate_username(client: AsyncClient):
    await _register(client, "bob")
    r = await client.post("/api/auth/register", json={"username": "bob", "password": "secret123"})
    assert r.status_code == 409


async def test_duplicate_email(client: AsyncClient):
    await _register(client, "carol", email="same@example.com")
    r = await client.post("/api/auth/register", json={"username": "carol2", "password": "secret123", "email": "same@example.com"})
    assert r.status_code == 409


async def test_refresh_roundtrip(client: AsyncClient):
    tokens = await _register(client, "dave")
    r = await client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    new = r.json()
    assert new["access_token"]
    # refresh token 轮换
    assert new["refresh_token"] != tokens["refresh_token"]


async def test_me_requires_auth(client: AsyncClient):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


async def test_users_isolated(client: AsyncClient):
    # 两个用户各自能通过自己的 token 访问 /me，互不干扰
    t1 = await _register(client, "user1")
    t2 = await _register(client, "user2")
    r1 = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {t1['access_token']}"})
    r2 = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {t2['access_token']}"})
    assert r1.json()["username"] == "user1"
    assert r2.json()["username"] == "user2"


async def _register(client: AsyncClient, username: str, **extra) -> dict:
    r = await client.post("/api/auth/register", json={"username": username, "password": "secret123", **extra})
    assert r.status_code == 201, r.text
    return r.json()
