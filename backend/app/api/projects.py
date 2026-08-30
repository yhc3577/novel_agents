from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import (
    Benchmark,
    Chapter,
    ChapterRecord,
    ChapterReview,
    Character,
    ContextView,
    DeslopRun,
    Foreshadowing,
    OutlineChapter,
    Project,
    ReferenceMaterial,
    Setting,
    Task,
    TimelineEvent,
    TrackingState,
    User,
    UserSetting,
    Volume,
)
from app.repositories.project import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


def _repo(db: AsyncSession) -> ProjectRepository:
    return ProjectRepository(db)


def _not_found() -> HTTPException:
    # 越权与不存在统一 404，不泄露租户存在性
    return HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")


@router.get("", response_model=list[ProjectOut])
async def list_projects(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _repo(db).list(user.id)


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    repo = _repo(db)
    if await repo.get_by_slug(user.id, payload.slug):
        raise HTTPException(status.HTTP_409_CONFLICT, "书名标识已存在")
    project = await repo.create(user.id, payload.model_dump())
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "书名标识已存在")
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    project = await _repo(db).get(user.id, project_id)
    if project is None:
        raise _not_found()
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _repo(db).update(user.id, project_id, payload.model_dump(exclude_unset=True))
    if project is None:
        raise _not_found()
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", response_model=ProjectOut)
async def delete_project(
    project_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """删除项目及其全部附属数据（章节/追踪/审查/去味/任务/大纲/设定/基准/参考素材等）。

    演示与长期运营都需要清理能力；按外键依赖顺序整树删除，跨 SQLite/PG 一致。
    """
    project = await _repo(db).get(user.id, project_id)
    if project is None:
        raise _not_found()
    # 1) 摘除 UserSetting 的默认项目引用（可空外键，置 NULL 而非删除）
    await db.execute(
        update(UserSetting).where(UserSetting.default_project_id == project_id).values(default_project_id=None)
    )
    # 2) 按外键依赖顺序删除项目附属行（子表 → 父表）
    #    大纲章节挂在卷下（volume_id 外键），先经卷 id 子查询删除，再删卷
    await db.execute(
        delete(OutlineChapter).where(
            OutlineChapter.volume_id.in_(select(Volume.id).where(Volume.project_id == project_id))
        )
    )
    for model in (
        ChapterRecord, ContextView, TimelineEvent, Foreshadowing, Character,
        TrackingState, ChapterReview, DeslopRun, Task, Chapter, Volume,
        Setting, Benchmark, ReferenceMaterial,
    ):
        await db.execute(delete(model).where(model.project_id == project_id))
    # 3) 删项目本身
    await db.delete(project)
    await db.commit()
    return project


@router.post("/{project_id}/activate", response_model=ProjectOut)
async def activate_project(
    project_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    project = await _repo(db).activate(user.id, project_id)
    if project is None:
        raise _not_found()
    await db.commit()
    await db.refresh(project)
    return project
