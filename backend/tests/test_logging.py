"""D11 验收（US-31）：request-id 中间件 + 未捕获异常统一 500。

- 每个 HTTP 响应带 `X-Request-ID`（16 位十六进制）；
- 未捕获异常 → 500 `{"code":"internal_error","message":...}`，日志带 request-id。
"""

from httpx import ASGITransport, AsyncClient


async def test_health_returns_request_id(client):
    r = await client.get("/health")
    assert r.status_code == 200
    rid = r.headers.get("x-request-id")
    assert rid and len(rid) == 16


async def test_api_404_returns_request_id(client):
    r = await client.get("/api/definitely-not-a-route")
    assert r.status_code == 404
    assert r.headers.get("x-request-id")


async def test_unhandled_exception_returns_500_json(client_app):
    @client_app.get("/boom")
    async def boom():
        raise RuntimeError("kaboom")

    async with AsyncClient(
        transport=ASGITransport(app=client_app, raise_app_exceptions=False), base_url="http://test"
    ) as ac:
        r = await ac.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["code"] == "internal_error"
    assert body["message"]  # debug=False 时是通用文案，不为空即可
    assert r.headers.get("x-request-id")
