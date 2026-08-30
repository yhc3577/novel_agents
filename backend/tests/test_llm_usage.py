"""ModelFactory：用量记录（含 cached_tokens）与跨 provider 降级。"""

from types import SimpleNamespace

from sqlalchemy import select

from app.core.crypto import encrypt_secret
from app.llm import ModelFactory
from app.models import Provider, UsageLog, User


def _fake_msg(content: str, usage: dict):
    return SimpleNamespace(content=content, response_metadata={"usage": usage})


class FakeChat:
    def __init__(self, reply):
        self.reply = reply

    async def ainvoke(self, messages):
        return self.reply


class RaisingChat:
    async def ainvoke(self, messages):
        raise RuntimeError("rate limited: 429")


async def _seed_provider(db, name: str, priority: int, models: dict | None = None):
    db.add(
        Provider(
            name=name,
            base_url=f"https://{name}.test/v1",
            api_key_enc=encrypt_secret("secret-key"),
            models=models or {"high": f"{name}-h", "mid": f"{name}-m", "low": f"{name}-l"},
            enabled=True,
            priority=priority,
        )
    )


async def _seed_user(db, name: str = "usg_user") -> User:
    user = User(username=name, password_hash="x")
    db.add(user)
    await db.flush()
    return user


async def test_invoke_records_usage_with_cached_tokens(db, monkeypatch):
    await _seed_provider(db, "fake", 0)
    user = await _seed_user(db)
    await db.flush()

    factory = ModelFactory(db, user.id)
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "prompt_tokens_details": {"cached_tokens": 7}}
    monkeypatch.setattr(factory, "_client", lambda pconf, model: FakeChat(_fake_msg("你好世界", usage)))

    text = await factory.invoke_with_retry("mid", [("human", "hi")], task_type="test_usage")
    await db.flush()

    assert text == "你好世界"
    row = await db.scalar(select(UsageLog).where(UsageLog.owner_id == user.id))
    assert row is not None
    assert row.provider == "fake"
    assert row.task_type == "test_usage"
    assert row.prompt_tokens == 10
    assert row.completion_tokens == 5
    assert row.cached_tokens == 7  # 缓存命中量正确落库


async def test_cached_tokens_falls_back_to_moonshot_key(db, monkeypatch):
    await _seed_provider(db, "kimi", 0)
    user = await _seed_user(db, "usg_kimi")
    await db.flush()

    factory = ModelFactory(db, user.id)
    usage = {"prompt_tokens": 3, "completion_tokens": 1, "prompt_cache_hit_tokens": 11}
    monkeypatch.setattr(factory, "_client", lambda pconf, model: FakeChat(_fake_msg("ok", usage)))

    await factory.invoke_with_retry("low", [("human", "hi")], task_type="test")
    await db.flush()

    row = await db.scalar(select(UsageLog).where(UsageLog.owner_id == user.id))
    assert row.cached_tokens == 11


async def test_cross_provider_downgrade(db, monkeypatch):
    """同 tier 首个 provider API 级失败 → 自动降级到次优 provider。"""
    await _seed_provider(db, "p_bad", 0)
    await _seed_provider(db, "p_good", 10)
    user = await _seed_user(db, "usg_downgrade")
    await db.flush()

    factory = ModelFactory(db, user.id)

    def client(pconf, model):
        if pconf.name == "p_bad":
            return RaisingChat()
        return FakeChat(_fake_msg("降级成功", {"prompt_tokens": 1, "completion_tokens": 1}))

    monkeypatch.setattr(factory, "_client", client)

    text = await factory.invoke_with_retry("mid", [("human", "hi")], task_type="test")
    await db.flush()

    assert text == "降级成功"
    row = await db.scalar(select(UsageLog).where(UsageLog.owner_id == user.id))
    assert row.provider == "p_good"
