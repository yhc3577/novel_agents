"""ChapterService（US-09）：草稿 → 字数收口 → 原子提交 → 接受自然长度。

commit 为写作链路唯一的章节提交入口：
质量门禁（QualityService）→ 追踪事务（TrackingService.commit）→ 标记 committed。
三者任一失败即整体回滚，保证"一次 commit 同时更新 chapters / 角色 / 伏笔 / 时间线 /
重建 chapter_records / context_views / revision+1"。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chapter, OutlineChapter, Project, Volume
from app.schemas.tracking import TrackingTx
from app.services.quality import QualityService
from app.services.tracking import TrackingService
from app.services.wordcount import WordcountService

# 细纲缺省目标字数（无显式目标时）
DEFAULT_TARGET_WORDCOUNT = 2000


class ChapterConflict(Exception):
    """章节状态不允许该操作"""


class ChapterService:
    def __init__(self, db: Session):
        self.db = db
        self.tracking = TrackingService(db)
        self.quality = QualityService(db)
        self.wordcount = WordcountService(db)

    # ---- 草稿 ----

    async def draft(
        self,
        project_id: int,
        chapter_no: int,
        content: str,
        title: str | None = None,
    ) -> Chapter:
        """存草稿 + 记字数（幂等，重复草稿覆盖）。"""
        ch = await self.db.scalar(
            select(Chapter).where(
                Chapter.project_id == project_id, Chapter.chapter_no == chapter_no
            )
        )
        if ch is None:
            vol = await self._find_volume(project_id, chapter_no)
            ch = Chapter(
                project_id=project_id,
                volume_id=vol.id if vol else None,
                chapter_no=chapter_no,
                title=title or f"第{chapter_no}章",
                content=content,
                status="draft",
            )
            self.db.add(ch)
        else:
            if title:
                ch.title = title
            ch.content = content
            ch.status = "draft"
        ch.wordcount = WordcountService.measure_text(content)
        await self.db.flush()
        return ch

    # ---- 字数 ----

    async def check(self, project_id: int, chapter_no: int) -> str:
        """in_range / under / over（对照大纲目标字数，非对称收口）。"""
        target = await self.target_wordcount(project_id, chapter_no)
        ch = await self._require(project_id, chapter_no)
        return WordcountService.evaluate_actual(ch.wordcount, target)

    async def accept_length(self, project_id: int, chapter_no: int) -> Chapter:
        """接受自然长度：标记大纲该章目标作废，后续提交不再催字数。"""
        ch = await self._require(project_id, chapter_no)
        oc = await self._outline_for(project_id, chapter_no)
        if oc is not None:
            beats = dict(oc.beats or {})
            beats["target_accepted"] = True
            oc.beats = beats
        ch.status = "draft"
        await self.db.flush()
        return ch

    async def target_wordcount(self, project_id: int, chapter_no: int) -> int:
        """细纲 beats['target_wordcount']，缺省取项目体裁默认。"""
        oc = await self._outline_for(project_id, chapter_no)
        if oc is not None and oc.beats and oc.beats.get("target_wordcount"):
            return int(oc.beats["target_wordcount"])
        return DEFAULT_TARGET_WORDCOUNT

    # ---- 原子提交 ----

    async def commit(
        self,
        project_id: int,
        chapter_no: int,
        tx: dict,
        *,
        expected_revision: int | None = None,
        fail_on: str = "none",
    ) -> Chapter:
        """原子提交：质量门禁 → 追踪事务 → 标记 committed。"""
        ch = await self._require(project_id, chapter_no)
        if ch.status == "committed" and not tx:
            raise ChapterConflict(f"章节 {chapter_no} 已提交，无变更可提交")

        # 1) 契约先校验（在写库前）
        TrackingTx.model_validate(tx)

        # 2) 质量门禁（blocking 失败 → 整体回滚）
        report = await QualityService(self.db).full_gate(ch.id, fail_on=fail_on)
        if report.blocking:
            raise ChapterConflict(f"质量门禁未过：{report.blocking[0].type}「{report.blocking[0].quote}」")

        # 3) 追踪事务（单事务，内部 commit）
        await self.tracking.commit(
            project_id,
            tx,
            expected_revision=expected_revision,
        )

        # 4) 标记提交（追踪 commit 已把 revision 推进，这里只需改状态）
        ch.status = "committed"
        ch.revision = ch.revision + 1
        await self.db.flush()
        await self.db.commit()
        return ch

    # ---- 内部 ----

    async def _require(self, project_id: int, chapter_no: int) -> Chapter:
        ch = await self.db.scalar(
            select(Chapter).where(
                Chapter.project_id == project_id, Chapter.chapter_no == chapter_no
            )
        )
        if ch is None:
            raise ChapterConflict(f"章节 {chapter_no} 不存在，请先 draft")
        return ch

    async def _find_volume(self, project_id: int, chapter_no: int) -> Volume | None:
        vol = await self.db.scalar(
            select(Volume)
            .where(Volume.project_id == project_id, Volume.no == 1)
            .order_by(Volume.no)
        )
        return vol

    async def _outline_for(self, project_id: int, chapter_no: int) -> OutlineChapter | None:
        vols = await self.db.scalars(select(Volume).where(Volume.project_id == project_id))
        vid = [v.id for v in vols]
        if not vid:
            return None
        return await self.db.scalar(
            select(OutlineChapter).where(
                OutlineChapter.volume_id.in_(vid), OutlineChapter.chapter_no == chapter_no
            )
        )
