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
from app.services.outline import project_outline
from app.services.task_service import TaskService
from app.services.tracking import TrackingService

router = APIRouter(tags=["writing"])


class NextChapterIn(BaseModel):
    action: str = Field(default="write_next", description="write_next/write_chapter/daily")
    scenario: str = Field(default="", max_length=2000)
    chapter_no: int | None = Field(default=None, ge=1)
    target: int | None = Field(default=None, ge=200, le=50000)
    resume_stage: str | None = Field(default=None, description="写作重试：从该开书阶段续跑（worldview/outline/beats）")


class OpenBookIn(BaseModel):
    scenario: str = Field(default="", max_length=2000, description="开书意图（无 key 时影响 stub 大纲）")
    force: bool = Field(default=False, description="true 时删除旧大纲重新生成")
    mode: str = Field(default="auto", description="auto=生成即入库；confirm=每阶段草稿待确认")
    stage: str = Field(default="all", description="all/worldview/outline/beats（重试从该阶段起跑）")


class DraftConfirmIn(BaseModel):
    action: str = Field(..., description="confirm=确认入库 / regenerate=重新生成 / cancel=取消")
    content: str | None = Field(default=None, description="确认时提交的草稿文本（可修改后入库）")


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


@router.post("/tasks/{task_id}/draft-confirm", response_model=TaskOut)
async def draft_confirm(
    task_id: int,
    payload: DraftConfirmIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """confirm 模式：唤醒暂停的开书任务。confirm 提交可编辑草稿；regenerate 重跑本阶段；cancel 取消。"""
    task = await _own_task(db, user, task_id)
    handle = TaskService().registry_get(task_id)
    if handle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在或已结束")
    if payload.action == "cancel":
        TaskService().cancel(task_id)
    else:
        handle.resume_payload = payload.model_dump()
        handle.resume_event.set()
    return TaskOut(id=task.id, type=task.type, status=task.status, progress=task.progress)


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


# ---- 开书（大纲） ----

@router.get("/projects/{project_id}/outline")
async def get_outline(
    project_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """读取项目开书大纲（卷 → 章 → 细纲），兼容开书 / 拆文导入两种 beats 形状。"""
    await _own_project(db, user, project_id)
    return await project_outline(db, project_id)


@router.post("/projects/{project_id}/open-book", response_model=TaskOut)
async def open_book(
    project_id: int,
    payload: OpenBookIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发起开书任务（后台执行）：世界观→大纲→细纲。auto 生成即入库；confirm 每阶段等确认；stage 指定重试起跑点。"""
    await _own_project(db, user, project_id)
    svc = TaskService()
    task = await svc.create(
        db,
        owner_id=user.id,
        project_id=project_id,
        type="open_book",
        payload=payload.model_dump(),
    )
    svc.launch(task.id, request.app.state.session_factory)
    return TaskOut(id=task.id, type=task.type, status=task.status, progress=task.progress)


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
