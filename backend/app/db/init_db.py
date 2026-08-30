"""容器/部署启动建表入口（幂等，等价本地 `Base.metadata.create_all`，只补缺失表）。

用法：`python -m app.db.init_db`（在迁移到位前保证表存在）。
"""

import asyncio

import app.models  # noqa: F401  注册全部模型到 Base.metadata
from app.db.base import Base
from app.db.engine import engine


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("database tables ensured")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
