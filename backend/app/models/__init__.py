# 集中导入所有模型，确保 Base.metadata 完整注册（Alembic autogenerate / create_all 依赖）
from app.models.analysis import (
    AnalysisAggregate,
    AnalysisBook,
    AnalysisChapter,
    AnalysisProgress,
    ScanResult,
)
from app.models.kv import KvCache, KvLock
from app.models.review import ChapterReview, DeslopRun
from app.models.provider import Provider
from app.models.project import Project
from app.models.setting import UserSetting
from app.models.story import Chapter, OutlineChapter, Setting, Volume
from app.models.task import Task
from app.models.tracking import (
    AuthorMemory,
    Benchmark,
    Character,
    ChapterRecord,
    ContextView,
    Foreshadowing,
    ReferenceMaterial,
    TimelineEvent,
    TrackingState,
)
from app.models.usage import UsageLog
from app.models.user import User

__all__ = [
    "AnalysisAggregate",
    "AnalysisBook",
    "AnalysisChapter",
    "AnalysisProgress",
    "AuthorMemory",
    "KvCache",
    "KvLock",
    "Benchmark",
    "Chapter",
    "ChapterRecord",
    "ChapterReview",
    "DeslopRun",
    "Character",
    "ContextView",
    "Foreshadowing",
    "OutlineChapter",
    "Project",
    "Provider",
    "ReferenceMaterial",
    "ScanResult",
    "Setting",
    "Task",
    "TimelineEvent",
    "TrackingState",
    "UsageLog",
    "User",
    "UserSetting",
    "Volume",
]
