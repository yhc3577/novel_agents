"""用量统计 API（D10：US-27）：token / 成本 / 缓存命中率 按天汇总。

- GET /usage?days=30 → 汇总卡片 + 每日曲线 + 按任务类型 / 按 provider 分布。
聚合在 Python 侧完成（用量行数不大），便于跨库（SQLite 测试 / PG）一致。
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import UsageLog, User

router = APIRouter(tags=["usage"])


@router.get("/usage")
async def get_usage(
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await db.scalars(
        select(UsageLog).where(UsageLog.owner_id == user.id, UsageLog.created_at >= since)
    )

    daily: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0, "cost": Decimal("0")}
    )
    by_task: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "tokens": 0, "cost": Decimal("0")}
    )
    by_provider: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "tokens": 0, "cost": Decimal("0")}
    )
    totals = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0, "cost": Decimal("0")}

    for r in rows:
        date_key = r.created_at.date().isoformat() if r.created_at else "unknown"
        tokens = r.prompt_tokens + r.completion_tokens
        cost = r.cost_estimate or Decimal("0")

        d = daily[date_key]
        d["calls"] += 1
        d["prompt_tokens"] += r.prompt_tokens
        d["completion_tokens"] += r.completion_tokens
        d["cached_tokens"] += r.cached_tokens
        d["cost"] += cost

        t = by_task[r.task_type]
        t["calls"] += 1
        t["tokens"] += tokens
        t["cost"] += cost

        p = by_provider[r.provider]
        p["calls"] += 1
        p["tokens"] += tokens
        p["cost"] += cost

        totals["calls"] += 1
        totals["prompt_tokens"] += r.prompt_tokens
        totals["completion_tokens"] += r.completion_tokens
        totals["cached_tokens"] += r.cached_tokens
        totals["cost"] += cost

    total_tokens = totals["prompt_tokens"] + totals["completion_tokens"]
    return {
        "days": days,
        "totals": {
            **totals,
            "tokens": total_tokens,
            "cost": float(totals["cost"]),
            "cache_hit_rate": round(
                totals["cached_tokens"] / total_tokens, 4
            ) if total_tokens else 0.0,
        },
        "daily": sorted(
            (
                {
                    "date": k,
                    "calls": v["calls"],
                    "prompt_tokens": v["prompt_tokens"],
                    "completion_tokens": v["completion_tokens"],
                    "tokens": v["prompt_tokens"] + v["completion_tokens"],
                    "cached_tokens": v["cached_tokens"],
                    "cost": float(v["cost"]),
                }
                for k, v in daily.items()
            ),
            key=lambda x: x["date"],
        ),
        "by_task_type": sorted(
            ({"task_type": k, **v, "cost": float(v["cost"])} for k, v in by_task.items()),
            key=lambda x: -x["tokens"],
        ),
        "by_provider": sorted(
            ({"provider": k, **v, "cost": float(v["cost"])} for k, v in by_provider.items()),
            key=lambda x: -x["tokens"],
        ),
    }
