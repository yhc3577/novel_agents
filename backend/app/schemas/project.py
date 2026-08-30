from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$", description="书名拼音/英文标识")
    title: str = Field(min_length=1, max_length=128)
    genre: str | None = Field(default=None, max_length=64)
    platform: str | None = Field(default=None, max_length=32)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=128)
    genre: str | None = Field(default=None, max_length=64)
    platform: str | None = Field(default=None, max_length=32)


class ProjectOut(BaseModel):
    id: int
    slug: str
    title: str
    genre: str | None
    platform: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
