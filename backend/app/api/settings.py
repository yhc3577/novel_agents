"""设置 API（D7：US-17）：provider 配置 + 三档模型选择 + 连通性测试。

api_key 落库加密（Fernet）；读取时只回 has_key，不回明文。
用户三档选择存 user_settings.tier_{high,mid,low} = "provider:model"，
由 ModelFactory._user_tier_override 在每次调用时读取生效——改完立即生效。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_secret
from app.core.deps import get_current_user
from app.db.session import get_db
from app.llm.factory import ModelFactory
from app.models import Provider, User, UserSetting

router = APIRouter(prefix="/settings", tags=["settings"])


class ProviderUpdate(BaseModel):
    base_url: str | None = Field(default=None, max_length=255)
    api_key: str | None = Field(default=None, max_length=2000, description="空字符串=清除，None=保留")
    models: dict[str, str] | None = None
    enabled: bool | None = None
    priority: int | None = None


class TiersUpdate(BaseModel):
    high: str | None = Field(default=None, max_length=128)
    mid: str | None = Field(default=None, max_length=128)
    low: str | None = Field(default=None, max_length=128)


def _masked(p: Provider) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "base_url": p.base_url,
        "has_key": bool(p.api_key_enc),
        "models": p.models or {},
        "enabled": p.enabled,
        "priority": p.priority,
    }


@router.get("")
async def get_settings(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(Provider).order_by(Provider.priority))
    us = await db.scalar(select(UserSetting).where(UserSetting.user_id == user.id))
    tiers = {
        "high": us.tier_high if us else None,
        "mid": us.tier_mid if us else None,
        "low": us.tier_low if us else None,
    }
    return {"providers": [_masked(p) for p in rows], "tiers": tiers}


@router.put("/providers/{provider_id}")
async def update_provider(
    provider_id: int,
    payload: ProviderUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    p = await db.get(Provider, provider_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "供应商不存在")
    if payload.api_key is not None:
        p.api_key_enc = encrypt_secret(payload.api_key) if payload.api_key else None
    if payload.base_url is not None:
        p.base_url = payload.base_url
    if payload.models is not None:
        p.models = payload.models
    if payload.enabled is not None:
        p.enabled = payload.enabled
    if payload.priority is not None:
        p.priority = payload.priority
    await db.commit()
    await db.refresh(p)
    return _masked(p)


@router.post("/providers/{provider_id}/test")
async def test_provider(
    provider_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    p = await db.get(Provider, provider_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "供应商不存在")
    model = (p.models or {}).get("mid") or (p.models or {}).get("low") or (p.models or {}).get("high")
    if not model:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "未配置模型，请先填写 models")
    ok, latency_ms, err = await ModelFactory(db, user.id).probe(p.name, model)
    return {"ok": ok, "provider": p.name, "model": model, "latency_ms": latency_ms, "error": err}


@router.put("/tiers")
async def update_tiers(
    payload: TiersUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    us = await db.scalar(select(UserSetting).where(UserSetting.user_id == user.id))
    if us is None:
        us = UserSetting(user_id=user.id)
        db.add(us)
    us.tier_high = payload.high
    us.tier_mid = payload.mid
    us.tier_low = payload.low
    await db.commit()
    await db.refresh(us)
    return {"high": us.tier_high, "mid": us.tier_mid, "low": us.tier_low}
