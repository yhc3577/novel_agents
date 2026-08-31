"""写作链路输出契约（D4：US-12/13 路由、开书、写章）。

所有 LLM 结构化输出节点统一走 generate_checked 后校验（§5.1 契约清单）。
"""

from pydantic import BaseModel, Field

from app.schemas.tracking import TrackingTx


class IntentResult(BaseModel):
    intent: str = Field(..., description="create_outline/write_chapter/review_chapter/analyze/scan/query/other")
    project_ref: str | None = None


class LengthDecision(BaseModel):
    book_type: str = Field(..., description="long/short")
    chapters: int = Field(..., ge=1, le=2000)


class SettingItem(BaseModel):
    kind: str = Field(..., max_length=32)
    title: str = Field(default="", max_length=128)
    content: str = ""


class WorldviewBeats(BaseModel):
    settings: list[SettingItem] = Field(default_factory=list)


class OutlineStructureChapter(BaseModel):
    chapter_no: int = Field(..., ge=1)
    title: str = Field(..., max_length=64)


class OutlineStructure(BaseModel):
    volume_no: int = Field(default=1, ge=1)
    volume_title: str = Field(default="第一卷")
    synopsis: str = ""
    chapters: list[OutlineStructureChapter] = Field(default_factory=list)


class ChapterBeats(BaseModel):
    chapter_no: int = Field(..., ge=1)
    title: str = ""
    summary: str = ""
    target_wordcount: int = Field(default=2000, ge=200, le=20000)
    points: list[str] = Field(default_factory=list)


class BeatsDetail(BaseModel):
    chapters: list[ChapterBeats] = Field(default_factory=list)


class WritePlan(BaseModel):
    purpose: str = Field(..., min_length=1)
    beats: list[str] = Field(..., min_length=1)
    recall_used: list[str] = Field(default_factory=list)
    target_length: int = Field(default=2000, ge=200)


class ChapterResult(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    tracking: TrackingTx
