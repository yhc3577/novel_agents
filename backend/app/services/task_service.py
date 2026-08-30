"""任务管理（US-14/15）：tasks 表 + asyncio 后台 + SSE 事件队列。

- 任务状态机：pending → running → success/failed/cancelled
- 每个任务一个 asyncio.Queue 接收图节点 emit 的 SSE 事件；SSE 端点按协议序列化
- 取消：设置 asyncio.Event，节点在各步间检查（GraphRuntime.check_cancel）
- 会话工厂可注入（API 层从 request.app.state.session_factory 读取，测试可覆盖）
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.graphs.ctx import GraphRuntime, TaskCancelled
from app.models import Task

_registry: dict[int, "TaskHandle"] = {}


@dataclass
class TaskHandle:
    task_id: int
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    background: asyncio.Task | None = None
    finished: bool = False


def registry() -> dict[int, TaskHandle]:
    return _registry


def _prune(keep: int = 200) -> None:
    """轻量清理已完成的 handle，防止进程内无限增长。"""
    stale = [tid for tid, h in _registry.items() if h.finished and (h.background is None or h.background.done())]
    for tid in stale:
        _registry.pop(tid, None)


class TaskService:
    """任务 CRUD + 调度（不持有 DB，方法都收 session）。"""

    async def create(
        self,
        db: AsyncSession,
        *,
        owner_id: int,
        project_id: int | None,
        type: str,
        payload: dict | None = None,
    ) -> Task:
        task = Task(owner_id=owner_id, project_id=project_id, type=type, status="pending", payload=payload)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    def launch(self, task_id: int, session_factory: async_sessionmaker) -> None:
        """把任务挂到当前事件循环后台执行。"""
        _prune()
        handle = _registry.setdefault(task_id, TaskHandle(task_id))
        handle.background = asyncio.create_task(run_task(task_id, session_factory))

    def cancel(self, task_id: int) -> bool:
        handle = _registry.get(task_id)
        if handle is None:
            return False
        handle.cancel_event.set()
        return True

    async def stream_events(self, task_id: int) -> AsyncIterator[dict]:
        """消费任务事件队列，`done` 后终止（SSE 端点使用）。

        兼容迟到订阅：任务已结束且队列排空时，直接补一个 done，避免永久阻塞。
        """
        handle = _registry.get(task_id)
        if handle is None:
            yield {"type": "error", "error": "任务不存在或已过期"}
            return
        while True:
            if handle.finished and handle.queue.empty():
                yield {"type": "done", "status": "late"}
                break
            payload = await handle.queue.get()
            yield payload
            if payload.get("type") == "done":
                break


async def run_task(task_id: int, session_factory: async_sessionmaker) -> None:
    """任务执行器：开新会话 → 构建图 → 跑完 → 更新任务状态。"""
    handle = _registry[task_id]
    async with session_factory() as db:
        task = await db.get(Task, task_id)
        if task is None:
            return
        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        await db.commit()

        runtime = GraphRuntime(
            db=db,
            user_id=task.owner_id,
            project_id=task.project_id or 0,
            task_id=task_id,
            emit=handle.queue.put_nowait,
            cancel_event=handle.cancel_event,
        )
        payload = task.payload or {}
        try:
            if task.type == "write_chapter":
                from app.graphs.write import build_write_graph

                graph = build_write_graph(runtime)
                await graph.ainvoke(
                    {
                        "user_id": task.owner_id,
                        "project_id": task.project_id,
                        "task_id": task_id,
                        "action": payload.get("action", "write_next"),
                        "scenario": payload.get("scenario", ""),
                        "chapter_no": payload.get("chapter_no"),
                        "target": payload.get("target"),
                    }
                )
            elif task.type == "router":
                from app.graphs.router import build_router_graph

                graph = build_router_graph(runtime)
                await graph.ainvoke(
                    {
                        "user_id": task.owner_id,
                        "project_id": task.project_id,
                        "user_intent": payload.get("user_intent", ""),
                        "scenario": payload.get("scenario", ""),
                        "action": payload.get("action", "write_chapter"),
                    }
                )
            elif task.type == "analyze":
                from app.graphs.analyze import build_analyze_graph

                graph = build_analyze_graph(runtime, payload.get("book_id"))
                await graph.ainvoke(
                    {
                        "user_id": task.owner_id,
                        "book_id": payload.get("book_id"),
                        "task_id": task_id,
                    }
                )
            else:
                raise ValueError(f"未知任务类型: {task.type}")
            task.status = "success"
            handle.queue.put_nowait({"type": "done", "status": "success"})
        except TaskCancelled:
            task.status = "cancelled"
            handle.queue.put_nowait({"type": "status", "status": "cancelled"})
            handle.queue.put_nowait({"type": "done", "status": "cancelled"})
        except Exception as e:  # noqa: BLE001
            task.status = "failed"
            task.error = str(e)[:2000]
            handle.queue.put_nowait({"type": "error", "error": str(e)})
            handle.queue.put_nowait({"type": "done", "status": "failed"})
        task.finished_at = datetime.now(timezone.utc)
        await db.commit()
    handle = _registry.get(task_id)
    if handle is not None:
        handle.finished = True
