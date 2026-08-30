"""拆文 API（D6：US-18）：上传整书文本 → 发起拆文任务 → 读快照/报告。

任务执行与 SSE 复用 /tasks/{id} 与 /tasks/{id}/events（writing.py）。
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.services.analysis import AnalysisService
from app.services.task_service import TaskService

router = APIRouter(tags=["analysis"])


class BookIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=128)
    genre: str | None = Field(default=None, max_length=64)
    source_text: str = Field(..., min_length=1, max_length=2_000_000)


class BookOut(BaseModel):
    id: int
    title: str
    genre: str | None = None
    status: str


class TaskOut(BaseModel):
    id: int
    type: str
    status: str
    progress: str | None = None
    error: str | None = None


async def _own_book(db: AsyncSession, user: User, book_id: int):
    book = await AnalysisService(db).get_owned(user.id, book_id)
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "拆文书不存在")
    return book


@router.post("/analysis/books", response_model=BookOut, status_code=201)
async def create_book(
    payload: BookIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    book = await AnalysisService(db).create_book(
        user.id, title=payload.title, genre=payload.genre, source_text=payload.source_text
    )
    return BookOut(id=book.id, title=book.title, genre=book.genre, status=book.status)


@router.get("/analysis/books", response_model=list[BookOut])
async def list_books(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    books = await AnalysisService(db).list_owned(user.id)
    return [BookOut(id=b.id, title=b.title, genre=b.genre, status=b.status) for b in books]


@router.post("/analysis/books/{book_id}/analyze", response_model=TaskOut)
async def analyze_book(
    book_id: int, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """发起拆文任务（后台执行）；前端用 /tasks/{id}/events 订阅 SSE 进度。"""
    await _own_book(db, user, book_id)
    svc = TaskService()
    task = await svc.create(db, owner_id=user.id, project_id=None, type="analyze", payload={"book_id": book_id})
    svc.launch(task.id, request.app.state.session_factory)
    return TaskOut(id=task.id, type=task.type, status=task.status, progress=task.progress)


@router.get("/analysis/books/{book_id}")
async def get_book(
    book_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """快照：书 + 章节 + 全部分维聚合 + 阶段进度（前端拆文页渲染）。"""
    await _own_book(db, user, book_id)
    snap = await AnalysisService(db).snapshot(user.id, book_id)
    return snap


@router.get("/analysis/books/{book_id}/report")
async def get_report(
    book_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await _own_book(db, user, book_id)
    snap = await AnalysisService(db).snapshot(user.id, book_id)
    report = (snap or {}).get("aggregates", {}).get("report")
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "报告尚未生成")
    return {"book_id": book_id, "report": report}
