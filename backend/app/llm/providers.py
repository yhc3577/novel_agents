"""供应商配置加载（providers 表 → ProviderConfig，api_key 解密）。"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret
from app.models import Provider


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    models: dict[str, str]  # {"high","mid","low"}
    enabled: bool
    priority: int

    def resolve_model(self, tier: str) -> str | None:
        return self.models.get(tier)


async def load_providers(db: AsyncSession) -> list[ProviderConfig]:
    rows = await db.scalars(select(Provider).order_by(Provider.priority))
    configs = []
    for row in rows:
        configs.append(
            ProviderConfig(
                name=row.name,
                base_url=row.base_url,
                api_key=decrypt_secret(row.api_key_enc) if row.api_key_enc else "",
                models=row.models or {},
                enabled=row.enabled,
                priority=row.priority,
            )
        )
    return configs
