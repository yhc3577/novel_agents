import os
import tempfile

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401  ensure models are registered
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app


@pytest.fixture
async def db_engine():
    """每个测试一个独立文件库 + NullPool：每次 checkout 新连接。

    后台任务会话与 HTTP 请求会话各自独立连接（与生产一致），
    避免共享单连接（StaticPool :memory:）时事务互相打断。
    """
    fd, path = tempfile.mkstemp(prefix="novel_agents_test_", suffix=".db")
    os.close(fd)
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        poolclass=NullPool,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
async def db(db_engine):
    """直接访问数据库的会话（与 client 同库，便于服务层/仓储测试）。"""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client_app(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _get_db():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _get_db
    # 后台任务（写章/SSE）与测试共用同一文件库
    app.state.session_factory = session_factory

    yield app

    app.dependency_overrides.clear()


@pytest.fixture
async def client(client_app):
    transport = ASGITransport(app=client_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def register(client: AsyncClient, username: str, password: str = "secret123", **extra) -> dict:
    r = await client.post("/api/auth/register", json={"username": username, "password": password, **extra})
    assert r.status_code == 201, r.text
    return r.json()
