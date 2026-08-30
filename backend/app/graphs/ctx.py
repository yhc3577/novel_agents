"""图运行时上下文：节点与 SSE 队列、DB 会话、取消信号之间的桥梁。

设计 §2.5 的 SSE 协议由节点通过 `ctx.emit` 直接推送（stage/tool/token/checkpoint/status），
执行器（task_service）负责把它们投递到任务的 asyncio.Queue，SSE 端点按协议序列化。
"""

import asyncio
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import ModelFactory

Emit = Callable[[dict], None]


class TaskCancelled(Exception):
    """任务取消（executor 抛给上层标记 cancelled）。"""


class GraphRuntime:
    def __init__(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        project_id: int,
        task_id: int | None = None,
        emit: Emit | None = None,
        cancel_event: asyncio.Event | None = None,
    ):
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        self.task_id = task_id
        self._emit: Emit = emit or (lambda _p: None)
        self.cancel_event = cancel_event or asyncio.Event()
        self._factory: ModelFactory | None = None

    # ---- SSE ----

    def emit(self, etype: str, **data) -> None:
        self._emit({"type": etype, **data})

    def emit_tool(self, name: str, action: str, duration_ms: int | None = None, output: str | None = None) -> None:
        payload: dict = {"type": "tool", "tool": name, "status": action}
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        if output is not None:
            payload["output"] = output
        self._emit(payload)

    # ---- 取消 ----

    @property
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def check_cancel(self) -> None:
        if self.cancel_event.is_set():
            raise TaskCancelled("任务已被用户取消")

    # ---- LLM ----

    @property
    def factory(self) -> ModelFactory:
        if self._factory is None:
            self._factory = ModelFactory(self.db, self.user_id)
        return self._factory

    # ---- 辅助 ----

    async def run_tool(self, name: str, fn: Callable[[], Awaitable]) -> object:
        """工具白名单封装：running →（执行）→ done，全程发 SSE 事件。"""
        import time

        self.check_cancel()
        self.emit_tool(name, "running")
        started = time.monotonic()
        try:
            result = await fn()
        except Exception as e:  # noqa: BLE001 工具失败也要体现在事件流里
            self.emit_tool(name, "error", duration_ms=int((time.monotonic() - started) * 1000), output=str(e))
            raise
        self.emit_tool(name, "done", duration_ms=int((time.monotonic() - started) * 1000))
        return result
