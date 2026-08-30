"""追踪事务契约（US-08）：LLM 输出的 JSON 先过契约，再校验，后入库。

设计 §3.3 契约清单：`TrackingTx{append:[...], revisions:[...]}`。
为避免冗余，这里把 append/revisions 合并为按域的列表，commit 阶段分别处理新增与修订。
"""

from pydantic import BaseModel, Field, model_validator


class CharacterTx(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    kind: str | None = Field(default=None, max_length=32)  # 主角/配角/反派/路人
    profile: dict | None = None  # 人物小传（自由键值）
    active_status: str | None = Field(default=None, max_length=16)  # active/deceased/absent
    revise: bool = False  # True=修订已有角色（按 name 定位）


class ForeshadowingTx(BaseModel):
    content: str = Field(..., min_length=1)
    planted_chapter: int | None = None  # 缺省=当前章
    resolved_chapter: int | None = None
    status: str = "planted"  # planted/resolved
    resolve_id: int | None = None  # 引爆已有伏笔（按 id 定位）


class TimelineTx(BaseModel):
    content: str = Field(..., min_length=1)
    chapter_no: int | None = None  # 缺省=当前章
    author_only: bool = False  # 仅作者可见（上帝视角，不随原文输出）


class TrackingTx(BaseModel):
    """一次章节提交携带的全部追踪更新，逐字由 LLM 契约节点产出。"""

    chapter_no: int = Field(..., ge=1)
    characters: list[CharacterTx] = Field(default_factory=list)
    foreshadowing: list[ForeshadowingTx] = Field(default_factory=list)
    timeline: list[TimelineTx] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_not_empty(self) -> "TrackingTx":
        # 允许空事务（纯字数提交），但任何列表内条目必须合法
        return self
