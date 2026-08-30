"""扫榜链路输出契约（D9：US-24，§5.1 契约清单）。"""

from pydantic import BaseModel, Field


class ScanBook(BaseModel):
    rank: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    author: str = Field(..., min_length=1)
    genre: str = Field(..., min_length=1)
    words: int = Field(..., ge=0)  # 字数（万字）
    followers: int = Field(..., ge=0)  # 收藏 / 在读
    growth_7d: int = Field(..., ge=0)  # 7 日新增收藏
    rating: float = Field(default=0, ge=0, le=10)
    tags: list[str] = Field(default_factory=list)


class ScanRankings(BaseModel):
    platform: str = Field(..., min_length=1)
    books: list[ScanBook] = Field(..., min_length=1)


class TrendReport(BaseModel):
    total: int = Field(..., ge=0)
    insights: str = Field(..., min_length=1)
    genre_distribution: list[dict] = Field(default_factory=list)
    hot_tags: list[dict] = Field(default_factory=list)
    top_books: list[str] = Field(default_factory=list)


class TopicDecision(BaseModel):
    topic: str = Field(..., min_length=1)
    genre: str = Field(..., min_length=1)
    rationale: str = Field(..., min_length=1)
    hooks: list[str] = Field(default_factory=list)
    risk: str = Field(default="", max_length=256)
    hot_tag: str = Field(default="", max_length=32)


class ScanReportOut(BaseModel):
    report: str = Field(..., min_length=1)
