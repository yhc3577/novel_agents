"""TrackingService（US-08）——追踪域唯一写入口。

铁律（架构 §3.2）：`tracking_state` 与派生视图（chapter_records / context_views）
只能由 TrackingService / ChapterService 写入。commit 全程单事务：
BEGIN → 锁项目行 FOR UPDATE → 契约校验 → 联动角色/伏笔/时间线 → 重建派生视图 →
revision+1 → COMMIT。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ChapterRecord,
    Character,
    ContextView,
    Foreshadowing,
    Project,
    TimelineEvent,
    TrackingState,
)
from app.schemas.tracking import TrackingTx


class TrackingConflict(Exception):
    """版本守卫冲突（并发提交 / 回放）"""


class TrackingValidationError(Exception):
    """契约通过但业务校验失败"""


class TrackingService:
    def __init__(self, db: Session):
        self.db = db

    # ---- 写前查询（工具白名单） ----

    async def check(self, project_id: int) -> dict:
        """只读状态：提交进度 + 版本 + 派生视图一致性。"""
        state = await self.db.scalar(
            select(TrackingState).where(TrackingState.project_id == project_id)
        )
        rev = state.state_revision if state else 0
        last = state.last_committed_chapter if state else 0
        view = await self.db.scalar(
            select(ContextView).where(ContextView.project_id == project_id)
        )
        return {
            "last_committed_chapter": last,
            "state_revision": rev,
            "views_consistent": bool(view and view.revision == rev and view.content),
        }

    # ---- 唯一写入口 ----

    async def init(self, project_id: int, input_json: dict) -> int:
        """开书时初始化追踪真值（revision=1），幂等。input_json 存初始快照。"""
        state = await self.db.scalar(
            select(TrackingState).where(TrackingState.project_id == project_id)
        )
        if state is not None:
            return state.state_revision
        state = TrackingState(
            project_id=project_id,
            state_revision=1,
            last_committed_chapter=0,
            state_jsonb=input_json,
        )
        self.db.add(state)
        await self.db.flush()
        return state.state_revision

    async def commit(
        self,
        project_id: int,
        transaction_json: dict,
        *,
        expected_revision: int | None = None,
    ) -> int:
        """单事务提交：契约校验 → 业务校验 → 联动更新 → 重建派生视图 → revision+1。

        - `expected_revision` 提供乐观锁：不等于当前 revision 即抛 TrackingConflict。
        - 任何一步失败整事务回滚，不产生半写状态。
        """
        # 契约校验（Pydantic，先于任何 DB 写）
        tx = TrackingTx.model_validate(transaction_json)

        try:
            # 锁项目行，串行化并发提交
            project = await self.db.scalar(
                select(Project).where(Project.id == project_id).with_for_update()
            )
            if project is None:
                raise TrackingValidationError(f"项目 {project_id} 不存在")

            state = await self.db.scalar(
                select(TrackingState)
                .where(TrackingState.project_id == project_id)
                .with_for_update()
            )
            if state is None:
                state = TrackingState(project_id=project_id, state_revision=0, last_committed_chapter=0)
                self.db.add(state)
                await self.db.flush()

            if expected_revision is not None and state.state_revision != expected_revision:
                raise TrackingConflict(
                    f"版本冲突：期望 revision={expected_revision}，实际={state.state_revision}"
                )

            # 章节连续性：可提交下一章，或重提交已有章节（revision 仅 track 次数）
            if tx.chapter_no < 1:
                raise TrackingValidationError(f"非法章节号 {tx.chapter_no}")

            await self._apply_tx(project_id, tx)

            # 版本推进
            state.state_revision += 1
            state.last_committed_chapter = max(state.last_committed_chapter, tx.chapter_no)
            state.state_jsonb = {"tx": tx.model_dump(), "chapter_no": tx.chapter_no}
            await self.db.flush()

            # 重建派生视图（同一事务内可见）
            await self._rebuild_derived(project_id, state)

            await self.db.commit()
            return state.state_revision
        except Exception:
            await self.db.rollback()
            raise

    # ---- 私有：事务应用 ----

    async def _apply_tx(self, project_id: int, tx: TrackingTx) -> None:
        for c in tx.characters:
            row = await self.db.scalar(
                select(Character).where(
                    Character.project_id == project_id, Character.name == c.name
                )
            )
            if row is None:
                row = Character(
                    project_id=project_id,
                    name=c.name,
                    kind=c.kind,
                    profile=c.profile,
                    active_status=c.active_status,
                )
                self.db.add(row)
            else:
                if c.revise or c.profile or c.kind or c.active_status:
                    if c.kind is not None:
                        row.kind = c.kind
                    if c.profile is not None:
                        row.profile = c.profile
                    if c.active_status is not None:
                        row.active_status = c.active_status
                else:
                    # 同名重复出现：保留首次定义，仅视为"提及"
                    continue

        for f in tx.foreshadowing:
            if f.resolve_id is not None:
                existing = await self.db.get(Foreshadowing, f.resolve_id)
                if existing and existing.project_id == project_id:
                    existing.status = "resolved"
                    existing.resolved_chapter = f.resolved_chapter or tx.chapter_no
                continue
            self.db.add(
                Foreshadowing(
                    project_id=project_id,
                    content=f.content,
                    planted_chapter=f.planted_chapter or tx.chapter_no,
                    resolved_chapter=f.resolved_chapter,
                    status=f.status,
                )
            )

        for t in tx.timeline:
            self.db.add(
                TimelineEvent(
                    project_id=project_id,
                    chapter_no=t.chapter_no or tx.chapter_no,
                    author_only=t.author_only,
                    content=t.content,
                )
            )

    async def _rebuild_derived(self, project_id: int, state: TrackingState) -> None:
        # chapter_records：当前章快照
        chars = await self.db.scalars(
            select(Character).where(Character.project_id == project_id)
        )
        events = await self.db.scalars(
            select(TimelineEvent)
            .where(TimelineEvent.project_id == project_id)
            .order_by(TimelineEvent.chapter_no)
        )
        fs = await self.db.scalars(
            select(Foreshadowing).where(Foreshadowing.project_id == project_id)
        )
        record = await self.db.scalar(
            select(ChapterRecord).where(
                ChapterRecord.project_id == project_id,
                ChapterRecord.chapter_no == state.last_committed_chapter,
            )
        )
        if record is None:
            record = ChapterRecord(
                project_id=project_id, chapter_no=state.last_committed_chapter
            )
            self.db.add(record)
        record.characters = {"active": [{"name": c.name, "kind": c.kind, "status": c.active_status} for c in chars]}
        record.events = [{"chapter_no": e.chapter_no, "author_only": e.author_only, "content": e.content} for e in events]
        record.foreshadowing = {
            "planted": [{"id": x.id, "content": x.content, "chapter": x.planted_chapter} for x in fs if x.status == "planted"],
            "resolved": [{"id": x.id, "content": x.content, "chapter": x.resolved_chapter} for x in fs if x.status == "resolved"],
        }

        # context_views：重建 7 列视图（内容委托 ContextService，避免循环导入）
        from app.services.context import ContextService

        content = await ContextService(self.db).build_context_view(project_id)
        view = await self.db.scalar(
            select(ContextView).where(ContextView.project_id == project_id)
        )
        if view is None:
            view = ContextView(project_id=project_id)
            self.db.add(view)
        view.revision = state.state_revision
        view.content = content
