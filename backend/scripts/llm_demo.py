"""CLI 演示（US-06 验收）：用已配置 provider 生成一句话并写 usage_logs。

用法：
    ./.venv/bin/python scripts/llm_demo.py --tier mid --text "写一句..."
    # 临时写入 provider 的 api_key（加密落库，供本地调试）：
    DEEPSEEK_API_KEY=sk-xxx ./.venv/bin/python scripts/llm_demo.py
    ./.venv/bin/python scripts/llm_demo.py --api-key sk-xxx --provider deepseek
"""

import argparse
import asyncio
import os

from sqlalchemy import select

from app.core.crypto import encrypt_secret
from app.core.security import hash_password
from app.db.engine import SessionLocal
from app.llm import ModelFactory
from app.models import Provider, UsageLog, User


async def ensure_user(db, username: str) -> User:
    user = await db.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(username=username, password_hash=hash_password("demo-password"), display_name="CLI demo")
        db.add(user)
        await db.flush()
    return user


async def ensure_key(db, provider: str, api_key: str) -> None:
    row = await db.scalar(select(Provider).where(Provider.name == provider))
    if row is None:
        print(f"[warn] provider '{provider}' 不存在，跳过写入 key")
        return
    row.api_key_enc = encrypt_secret(api_key)
    await db.flush()
    print(f"[info] 已写入 provider '{provider}' 的 api_key（Fernet 加密）")


async def main() -> None:
    ap = argparse.ArgumentParser(description="LLM 一句话生成 + 用量记录演示")
    ap.add_argument("--tier", default="mid", choices=["low", "mid", "high"])
    ap.add_argument("--provider", default="deepseek")
    ap.add_argument("--api-key", default=None, help="临时写入 provider 的 api_key")
    ap.add_argument("--user", default="cli_demo")
    ap.add_argument("--text", default="写一句玄幻小说的开篇：主角穿越到修仙世界，睁开眼发现自己正在悬崖边。")
    args = ap.parse_args()

    api_key = args.api_key or os.getenv(f"{args.provider.upper()}_API_KEY")
    if not api_key:
        print("[warn] 未提供 api_key（--api-key 或环境变量），将使用 providers 表中已配置的 key（当前为空）")

    async with SessionLocal() as db:
        user = await ensure_user(db, args.user)
        if api_key:
            await ensure_key(db, args.provider, api_key)
        await db.commit()

        factory = ModelFactory(db, user.id)
        text = await factory.invoke_with_retry(args.tier, [("human", args.text)], task_type="cli_demo")
        await db.commit()

        print(f"--- 生成结果 [{args.tier}] ---")
        print(text)
        print("--- 最近 usage_logs ---")
        rows = await db.scalars(
            select(UsageLog).where(UsageLog.owner_id == user.id).order_by(UsageLog.id.desc()).limit(1)
        )
        for row in rows:
            print(
                f"provider={row.provider} model={row.model} "
                f"prompt={row.prompt_tokens} completion={row.completion_tokens} "
                f"cached={row.cached_tokens} latency={row.latency_ms}ms"
            )


if __name__ == "__main__":
    asyncio.run(main())
