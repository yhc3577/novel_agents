"""写作闭环 API（US-14/15）：任务启停、SSE 事件流、章节与追踪上下文读取。"""

import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Chapter, ContextView, Project, Task, TrackingState, User
from app.services.context import ContextService
from app.services.task_service import TaskService
from app.services.tracking import TrackingService

router = APIRouter(tags=["writing"])


class NextChapterIn(BaseModel):
    action: str = Field(default="write_next", description="write_next/write_chapter/daily")
    scenario: str = Field(default="", max_length=2000)
    chapter_no: int | None = Field(default=None, ge=1)
    target: int | None = Field(default=None, ge=200, le=50000)


class TaskOut(BaseModel):
    id: int
    type: str
    status: str
    progress: str | None = None
    error: str | None = None
    started_at: object | None = None
    finished_at: object | None = None


class ChapterOut(BaseModel):
    chapter_no: int
    title: str
    wordcount: int
    status: str
    revision: int


async def _own_project(db: AsyncSession, user: User, project_id: int) -> Project:
    project = await db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    return project


async def _own_task(db: AsyncSession, user: User, task_id: int) -> Task:
    task = await db.get(Task, task_id)
    if task is None or task.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    return task


# ---- 任务 ----

@router.post("/projects/{project_id}/chapters/next", response_model=TaskOut)
async def next_chapter(
    project_id: int,
    payload: NextChapterIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发起写一章任务（后台执行），返回 task_id；前端用 /tasks/{id}/events 订阅 SSE。"""
    await _own_project(db, user, project_id)
    svc = TaskService()
    task = await svc.create(
        db,
        owner_id=user.id,
        project_id=project_id,
        type="write_chapter",
        payload=payload.model_dump(),
    )
    svc.launch(task.id, request.app.state.session_factory)
    return TaskOut(id=task.id, type=task.type, status=task.status, progress=task.progress)


@router.get("/tasks/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    task = await _own_task(db, user, task_id)
    return TaskOut(
        id=task.id, type=task.type, status=task.status, progress=task.progress, error=task.error,
        started_at=task.started_at, finished_at=task.finished_at,
    )


@router.post("/tasks/{task_id}/cancel", response_model=TaskOut)
async def cancel_task(
    task_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    task = await _own_task(db, user, task_id)
    ok = TaskService().cancel(task_id)
    return TaskOut(id=task.id, type=task.type, status=task.status, progress=task.progress, error="已请求取消" if ok else None)


@router.get("/tasks/{task_id}/events")
async def task_events(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE 事件流：stage → tool → token → checkpoint → status → done/error。"""
    await _own_task(db, user, task_id)

    async def gen() -> AsyncIterator[str]:
        async for payload in TaskService().stream_events(task_id):
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---- 章节 / 追踪读取 ----

@router.get("/projects/{project_id}/chapters", response_model=list[ChapterOut])
async def list_chapters(
    project_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await _own_project(db, user, project_id)
    rows = await db.scalars(
        select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_no)
    )
    return [
        ChapterOut(chapter_no=c.chapter_no, title=c.title, wordcount=c.wordcount, status=c.status, revision=c.revision)
        for c in rows
    ]


@router.get("/projects/{project_id}/chapters/{chapter_no}")
async def get_chapter(
    project_id: int,
    chapter_no: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _own_project(db, user, project_id)
    ch = await db.scalar(
        select(Chapter).where(Chapter.project_id == project_id, Chapter.chapter_no == chapter_no)
    )
    if ch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "章节不存在")
    return {
        "chapter_no": ch.chapter_no,
        "title": ch.title,
        "content": ch.content or "",
        "wordcount": ch.wordcount,
        "status": ch.status,
        "revision": ch.revision,
    }


@router.get("/projects/{project_id}/tracking/context")
async def tracking_context(
    project_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """上下文视图（7 列 ≤12KB）：优先返回已重建的持久视图，无则现建。"""
    await _own_project(db, user, project_id)
    view = await db.scalar(select(ContextView).where(ContextView.project_id == project_id))
    if view is not None and view.content:
        return {"revision": view.revision, "content": view.content}
    return {"revision": 0, "content": await ContextService(db).build_context_view(project_id)}


@router.get("/projects/{project_id}/tracking")
async def tracking_info(
    project_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await _own_project(db, user, project_id)
    return await TrackingService(db).check(project_id)
