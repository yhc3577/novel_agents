"""扫榜 API（D9：US-24/25）：发起扫榜任务 → 读每平台最新快照/历史。

任务执行与 SSE 复用 /tasks/{id} 与 /tasks/{id}/events（writing.py）。
"""

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.graphs.stub_scan import PLATFORMS
from app.models import ScanResult, User
from app.services.task_service import TaskService

router = APIRouter(tags=["scan"])


class ScanRunIn(BaseModel):
    platforms: list[str] | None = Field(default=None)


class TaskOut(BaseModel):
    id: int
    type: str
    status: str
    progress: str | None = None
    error: str | None = None


def _out(r: ScanResult) -> dict:
    return {
        "id": r.id,
        "platform": r.platform,
        "snapshot_at": r.snapshot_at.isoformat() if r.snapshot_at else None,
        "raw": r.raw,
        "cleaned": r.cleaned,
        "report": r.report,
    }


@router.post("/scan/runs", response_model=TaskOut)
async def run_scan(
    payload: ScanRunIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发起扫榜任务（后台执行，两平台缺省；前端用 /tasks/{id}/events 订阅 SSE）。"""
    platforms = payload.platforms or list(PLATFORMS)
    invalid = [p for p in platforms if p not in PLATFORMS]
    if invalid:
        from fastapi import HTTPException, status

        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"未知平台: {invalid}")
    svc = TaskService()
    task = await svc.create(
        db, owner_id=user.id, project_id=None, type="scan", payload={"platforms": platforms}
    )
    svc.launch(task.id, request.app.state.session_factory)
    return TaskOut(id=task.id, type=task.type, status=task.status, progress=task.progress)


@router.get("/scan/results")
async def list_results(
    platform: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """历史快照（按时间倒序，可选平台过滤）。"""
    q = select(ScanResult).where(ScanResult.owner_id == user.id).order_by(ScanResult.id.desc()).limit(limit)
    if platform:
        q = q.where(ScanResult.platform == platform)
    rows = await db.scalars(q)
    return [_out(r) for r in rows]


@router.get("/scan/latest")
async def latest(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """每个平台的最新一条快照（前端扫榜页主视图）。"""
    rows = await db.scalars(
        select(ScanResult).where(ScanResult.owner_id == user.id).order_by(ScanResult.id.desc())
    )
    latest_by_platform: dict[str, dict] = {}
    for r in rows:
        if r.platform not in latest_by_platform:
            latest_by_platform[r.platform] = _out(r)
    return {"platforms": [latest_by_platform[p] for p in PLATFORMS if p in latest_by_platform]}
