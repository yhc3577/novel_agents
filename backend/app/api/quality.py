"""审查 + 去味 API（D8：US-21/22/23）。

审查/去味以后台任务运行（SSE 订阅 /tasks/{id}/events）；结果分别落
chapter_reviews / deslop_runs。accept 端点把去味 rewritten 写回 committed 行。
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Chapter, ChapterReview, DeslopRun, User
from app.services.task_service import TaskService
from app.services.wordcount import measure_text

router = APIRouter(tags=["quality"])


class ReviewIn(BaseModel):
    mode: str = Field(default="full", pattern="^(full|lean|solo)$")


class TaskOut(BaseModel):
    id: int
    type: str
    status: str
    progress: str | None = None
    error: str | None = None


async def _own_chapter(db: AsyncSession, user: User, project_id: int, chapter_no: int) -> Chapter:
    ch = await db.scalar(
        select(Chapter).where(Chapter.project_id == project_id, Chapter.chapter_no == chapter_no)
    )
    # 项目归属校验
    from app.models import Project

    proj = await db.get(Project, project_id)
    if proj is None or proj.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    if ch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "章节不存在")
    return ch


@router.post("/projects/{project_id}/chapters/{chapter_no}/review", response_model=TaskOut)
async def run_review(
    project_id: int,
    chapter_no: int,
    payload: ReviewIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _own_chapter(db, user, project_id, chapter_no)
    svc = TaskService()
    task = await svc.create(
        db, owner_id=user.id, project_id=project_id, type="review", payload={"chapter_no": chapter_no, "mode": payload.mode}
    )
    svc.launch(task.id, request.app.state.session_factory)
    return TaskOut(id=task.id, type=task.type, status=task.status, progress=task.progress)


@router.get("/projects/{project_id}/chapters/{chapter_no}/reviews")
async def list_reviews(
    project_id: int, chapter_no: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await _own_chapter(db, user, project_id, chapter_no)
    rows = await db.scalars(
        select(ChapterReview)
        .where(ChapterReview.project_id == project_id, ChapterReview.chapter_no == chapter_no)
        .order_by(ChapterReview.id.desc())
    )
    return [
        {
            "mode": r.mode, "score": r.score, "verdict": r.verdict,
            "findings": r.findings or [], "summary": r.summary,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/projects/{project_id}/chapters/{chapter_no}/deslop", response_model=TaskOut)
async def run_deslop(
    project_id: int,
    chapter_no: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _own_chapter(db, user, project_id, chapter_no)
    svc = TaskService()
    task = await svc.create(db, owner_id=user.id, project_id=project_id, type="deslop", payload={"chapter_no": chapter_no})
    svc.launch(task.id, request.app.state.session_factory)
    return TaskOut(id=task.id, type=task.type, status=task.status, progress=task.progress)


@router.get("/projects/{project_id}/chapters/{chapter_no}/deslop")
async def get_deslop(
    project_id: int, chapter_no: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """去味结果：original vs rewritten（deslop_runs）+ 定级。"""
    await _own_chapter(db, user, project_id, chapter_no)
    run = await db.scalar(select(DeslopRun).where(DeslopRun.project_id == project_id, DeslopRun.chapter_no == chapter_no))
    if run is None or not run.rewritten:
        return {"ready": False, "reason": "尚无去味结果"}
    original = run.original or ""
    rewritten = run.rewritten
    return {
        "ready": True,
        "grade": run.grade,
        "score": run.score,
        "findings": run.findings or [],
        "original_wordcount": measure_text(original),
        "new_wordcount": measure_text(rewritten),
        "delta_wordcount": measure_text(rewritten) - measure_text(original),
        "original": original,
        "rewritten": rewritten,
    }


@router.post("/projects/{project_id}/chapters/{chapter_no}/deslop/accept")
async def accept_deslop(
    project_id: int, chapter_no: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """接受去味：把 rewritten 写回 committed 行并 revision+1（无结果时 400）。"""
    await _own_chapter(db, user, project_id, chapter_no)
    run = await db.scalar(select(DeslopRun).where(DeslopRun.project_id == project_id, DeslopRun.chapter_no == chapter_no))
    if run is None or not run.rewritten:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "没有可接受的去味结果")
    ch = await db.scalar(
        select(Chapter).where(Chapter.project_id == project_id, Chapter.chapter_no == chapter_no)
    )
    if ch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "章节不存在")
    ch.content = run.rewritten
    ch.wordcount = measure_text(run.rewritten)
    ch.revision += 1
    ch.status = "committed"
    await db.commit()
    return {"chapter_no": chapter_no, "status": ch.status, "revision": ch.revision, "wordcount": ch.wordcount}
