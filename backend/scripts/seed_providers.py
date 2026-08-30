"""首启种子：config/models.yaml → providers 表（幂等，按 name upsert）。"""

import asyncio

import yaml
from sqlalchemy import select

from app.core.config import get_settings
from app.core.crypto import encrypt_secret
from app.db.engine import SessionLocal
from app.models import Provider


def load_models_yaml(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["providers"]


async def seed() -> int:
    settings = get_settings()
    specs = load_models_yaml(settings.models_yaml)
    count = 0
    async with SessionLocal() as db:
        for spec in specs:
            existing = await db.scalar(select(Provider).where(Provider.name == spec["name"]))
            if existing is None:
                db.add(
                    Provider(
                        name=spec["name"],
                        base_url=spec["base_url"],
                        api_key_enc=encrypt_secret(spec["api_key"]) if spec.get("api_key") else None,
                        models=spec["models"],
                        enabled=spec.get("enabled", True),
                        priority=spec.get("priority", 0),
                    )
                )
                count += 1
        await db.commit()
    return count


if __name__ == "__main__":
    n = asyncio.run(seed())
    print(f"seeded {n} providers")
