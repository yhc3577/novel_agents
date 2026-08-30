from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Project, User
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
