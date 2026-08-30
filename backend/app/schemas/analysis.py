"""拆文链路输出契约（D6：US-18，§5.1 契约清单）。"""

from pydantic import BaseModel, Field


class ChapterBoundary(BaseModel):
    no: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)


class ChapterBoundaries(BaseModel):
    chapters: list[ChapterBoundary] = Field(..., min_length=1)


class ChapterExtraction(BaseModel):
    chapter_no: int = Field(..., ge=1)
    summary: str = Field(..., min_length=1)
    beats: list[str] = Field(..., min_length=1)
    mood: str = Field(default="", max_length=128)
    hooks: list[str] = Field(default_factory=list)


class AnalysisOut(BaseModel):
    analysis: str = Field(..., min_length=1)
