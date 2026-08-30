from sqlalchemy import select, update

from app.models import Project
from app.repositories.base import OwnerRepo


class ProjectRepository(OwnerRepo):
    async def list(self, owner_id: int) -> list[Project]:
        rows = await self.db.scalars(
            select(Project).where(Project.owner_id == owner_id).order_by(Project.created_at.desc())
        )
        return list(rows)

    async def get(self, owner_id: int, project_id: int) -> Project | None:
        return await self.db.scalar(
            select(Project).where(Project.id == project_id, Project.owner_id == owner_id)
        )

    async def get_by_slug(self, owner_id: int, slug: str) -> Project | None:
        return await self.db.scalar(select(Project).where(Project.owner_id == owner_id, Project.slug == slug))

    async def create(self, owner_id: int, data: dict) -> Project:
        project = Project(owner_id=owner_id, **data)
        self.db.add(project)
        await self.db.flush()
        return project

    async def update(self, owner_id: int, project_id: int, fields: dict) -> Project | None:
        project = await self.get(owner_id, project_id)
        if project is None:
            return None
        for key, value in fields.items():
            if value is not None:
                setattr(project, key, value)
        await self.db.flush()
        return project

    async def activate(self, owner_id: int, project_id: int) -> Project | None:
        """设为活跃书：本项目置 active，其余置 inactive（同一事务，由调用方 commit）。"""
        project = await self.get(owner_id, project_id)
        if project is None:
            return None
        await self.db.execute(update(Project).where(Project.owner_id == owner_id).values(status="inactive"))
        project.status = "active"
        await self.db.flush()
        return project

    async def active(self, owner_id: int) -> Project | None:
        return await self.db.scalar(
            select(Project).where(Project.owner_id == owner_id, Project.status == "active")
        )
