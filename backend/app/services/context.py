"""ContextService（US-11）+ MemoryService：写前召回包装配 + 上下文视图。

context_views 固定 7 列 ≤12KB：大纲 / 最近章节 / 角色 / 伏笔 / 时间线 / 设定 / 作者记忆。
recall_pack 在写每一章前组装，随 tracking 段注入 prompt（段 3）。
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AuthorMemory,
    Chapter,
    Character,
    ContextView,
    Foreshadowing,
    OutlineChapter,
    Project,
    Setting,
    TimelineEvent,
    Volume,
)

# 7 列视图容量上限（字节，中文按 UTF-8 粗略）
MAX_VIEW_BYTES = 12 * 1024


class ContextService:
    def __init__(self, db: Session):
        self.db = db

    async def recall_pack(self, project_id: int) -> dict:
        """写前召回包：上下文视图 + 情绪模块 + 节奏 + 风格 + 题材卡。"""
        project = await self.db.get(Project, project_id)
        settings = {}
        rows = await self.db.scalars(
            select(Setting).where(Setting.project_id == project_id)
        )
        for s in rows:
            settings.setdefault(s.kind, []).append({"title": s.title, "content": s.content})

        def _pick(kind: str) -> str | None:
            for item in settings.get(kind, []):
                if item["content"]:
                    return item["content"]
            return None

        return {
            "context_view": await self.build_context_view(project_id),
            "emotion_module": _pick("emotion_module"),
            "rhythm": _pick("rhythm"),
            "style": _pick("style"),
            "topic_card": (
                f"{project.title}｜{project.genre or ''}｜{project.platform or ''}"
                if project
                else ""
            ),
        }

    async def build_context_view(self, project_id: int) -> str:
        """7 列 ≤12KB：大纲 / 最近章节 / 角色 / 伏笔 / 时间线 / 设定 / 作者记忆。"""
        project = await self.db.get(Project, project_id)
        owner_id = project.owner_id if project else None
        sections: list[tuple[str, str]] = [
            ("大纲", await self._outline(project_id)),
            ("最近章节", await self._recent_chapters(project_id)),
            ("角色", await self._characters(project_id)),
            ("伏笔", await self._foreshadowing(project_id)),
            ("时间线", await self._timeline(project_id)),
            ("设定", await self._settings(project_id)),
            ("作者记忆", await self._memory(owner_id)),
        ]
        parts = []
        used = 0
        for title, body in sections:
            budget = MAX_VIEW_BYTES - used
            if budget <= 0:
                break
            body = self._clip(body, budget)
            chunk = f"【{title}】{body}\n"
            parts.append(chunk)
            used += len(chunk.encode("utf-8"))
        return "".join(parts)

    # ---- 各列 ----

    async def _outline(self, project_id: int) -> str:
        vols = await self.db.scalars(select(Volume).where(Volume.project_id == project_id))
        vid = [v.id for v in vols]
        if not vid:
            return ""
        oc = await self.db.scalars(
            select(OutlineChapter).where(OutlineChapter.volume_id.in_(vid)).order_by(OutlineChapter.chapter_no)
        )
        return "；".join(
            f"第{c.chapter_no}章 {c.title}"
            + (f"：{c.beats['summary']}" if c.beats and c.beats.get("summary") else "")
            for c in oc
        )

    async def _recent_chapters(self, project_id: int) -> str:
        rows = (
            await self.db.scalars(
                select(Chapter)
                .where(Chapter.project_id == project_id, Chapter.status == "committed")
                .order_by(Chapter.chapter_no.desc())
                .limit(3)
            )
        ).all()
        return "；".join(f"第{c.chapter_no}章 {c.title}（{c.wordcount}字）" for c in reversed(rows))

    async def _characters(self, project_id: int) -> str:
        rows = await self.db.scalars(select(Character).where(Character.project_id == project_id))
        return "；".join(
            f"{c.name}（{c.kind or ''}{f'·{c.active_status}' if c.active_status else ''}）" for c in rows
        )

    async def _foreshadowing(self, project_id: int) -> str:
        rows = await self.db.scalars(
            select(Foreshadowing)
            .where(Foreshadowing.project_id == project_id, Foreshadowing.status == "planted")
            .order_by(Foreshadowing.planted_chapter)
        )
        return "；".join(f"[第{x.planted_chapter}章埋] {x.content}" for x in rows)

    async def _timeline(self, project_id: int) -> str:
        rows = await self.db.scalars(
            select(TimelineEvent)
            .where(TimelineEvent.project_id == project_id)
            .order_by(TimelineEvent.chapter_no.desc())
            .limit(10)
        )
        return "；".join(f"第{e.chapter_no}章 {e.content}" for e in reversed(list(rows)))

    async def _settings(self, project_id: int) -> str:
        rows = await self.db.scalars(select(Setting).where(Setting.project_id == project_id))
        return "；".join(
            f"{s.kind}/{s.title}：{s.content}" for s in rows if s.content
        )

    async def _memory(self, owner_id: int | None) -> str:
        if owner_id is None:
            return ""
        rows = await self.db.scalars(
            select(AuthorMemory)
            .where(AuthorMemory.owner_id == owner_id, AuthorMemory.active.is_(True))
            .order_by(AuthorMemory.id.desc())
            .limit(5)
        )
        return "；".join(f"[{m.kind}] {m.content}" for m in reversed(list(rows)))

    @staticmethod
    def _clip(text: str, budget_bytes: int) -> str:
        """按 UTF-8 字节预算截断，避免截断中文字符。"""
        if not text:
            return ""
        if len(text.encode("utf-8")) <= budget_bytes:
            return text
        out = ""
        size = 0
        for ch in text:
            b = len(ch.encode("utf-8"))
            if size + b > budget_bytes:
                break
            out += ch
            size += b
        return out + "…"


class MemoryService:
    """作者记忆（US-11 配套）：跨项目用户记忆，限 KB 查询。"""

    def __init__(self, db: Session):
        self.db = db

    async def record(self, owner_id: int, kind: str, content: str, scope: str | None = None) -> AuthorMemory:
        m = AuthorMemory(owner_id=owner_id, kind=kind, content=content, scope=scope, active=True)
        self.db.add(m)
        await self.db.flush()
        return m

    async def query(self, owner_id: int, kinds: list[str], limit_kb: float = 2.0) -> list[AuthorMemory]:
        rows = await self.db.scalars(
            select(AuthorMemory)
            .where(AuthorMemory.owner_id == owner_id, AuthorMemory.active.is_(True))
            .where(AuthorMemory.kind.in_(kinds))
            .order_by(AuthorMemory.id.desc())
        )
        out = []
        used = 0.0
        for m in reversed(list(rows)):
            kb = len((m.content or "").encode("utf-8")) / 1024
            if used + kb > limit_kb:
                continue
            out.append(m)
            used += kb
        return out
