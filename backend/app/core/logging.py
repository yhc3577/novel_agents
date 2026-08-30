"""结构化日志 + request-id（D11：US-31）。

- `request_id_var`：ContextVar，请求级唯一 id（后台任务不带请求时为 `-`）。
- `setup_logging()`：root logger 带 `req=<request-id>` 的统一格式。
- `RequestIDMiddleware`：每个 HTTP 请求生成 id，注入 ContextVar 并回写 `X-Request-ID` 响应头。
"""

from __future__ import annotations

import contextvars
import logging
import sys
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIDFormatter(logging.Formatter):
    """在 record 上补 request_id，供统一格式引用。"""

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get()
        return super().format(record)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        RequestIDFormatter("[%(asctime)s %(levelname)s req=%(request_id)s %(name)s] %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # uvicorn 日志走同一根 logger，避免重复 handler
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True


class RequestIDMiddleware:
    """ASGI 中间件：注入 request-id 并回写响应头。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        rid = uuid.uuid4().hex[:16]
        # 写入 scope state：异常处理器在中间件 finally（重置 contextvar）之后仍能读到同一 id
        state = scope.setdefault("state", {})
        state["request_id"] = rid
        token = request_id_var.set(rid)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"].append((b"X-Request-ID", rid.encode("ascii")))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_var.reset(token)
