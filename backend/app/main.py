import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import RequestIDMiddleware, request_id_var, setup_logging
from app.db.engine import SessionLocal

settings = get_settings()
setup_logging()
logger = logging.getLogger("app")


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    # 后台任务（写作/拆文等）使用的会话工厂；测试可覆盖为内存库
    app.state.session_factory = SessionLocal

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # request-id 注入（在 CORS 之后注册，位于最外层，先为请求分配 id）
    app.add_middleware(RequestIDMiddleware)

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health")
    async def health():
        return {"status": "ok", "app": settings.app_name}

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """未捕获异常：记录 request-id + traceback，统一返回 500（错误模型见详细设计 §10）。"""
        rid = request.scope.get("state", {}).get("request_id", request_id_var.get())
        token = request_id_var.set(rid)
        try:
            logger.error("unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        finally:
            request_id_var.reset(token)
        detail = str(exc) if settings.debug else "内部错误，请稍后重试"
        return JSONResponse(
            status_code=500,
            content={"code": "internal_error", "message": detail, "detail": detail},
            headers={"X-Request-ID": rid} if rid else None,
        )

    return app


app = create_app()
