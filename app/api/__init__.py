"""HTTP API 入口包。

按业务域拆到 routers/ 子模块；这里负责：

* 创建 ``FastAPI`` 实例并挂中间件
* ``include_router`` 聚合所有 router
* 挂载 SPA 静态托管（仅生产）
* 暴露兼容符号 ``app``、``ALLOWED_PROVIDERS``、``WORKER_NAMES``，
  满足 ``main.py`` 的 ``from app.api import app as api_app``。
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.chat import WORKER_NAMES as _WORKER_NAMES
from app.api.routers.chat import router as chat_router
from app.api.routers.eval import router as eval_router
from app.api.routers.kb import router as kb_router
from app.api.routers.monitor import router as monitor_router
from app.api.routers.static import mount_spa
from app.api.routers.status import router as status_router
from app.api.sse import ALLOWED_PROVIDERS as _ALLOWED_PROVIDERS

# 兼容外部脚本可能直接 ``from app.api import ALLOWED_PROVIDERS, WORKER_NAMES``
ALLOWED_PROVIDERS = _ALLOWED_PROVIDERS
WORKER_NAMES = _WORKER_NAMES

__all__ = [
    "app",
    "ALLOWED_PROVIDERS",
    "WORKER_NAMES",
]


def _create_app() -> FastAPI:
    application = FastAPI(title="Multi-Agent RAG Supervisor API", version="1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(chat_router)
    application.include_router(kb_router)
    application.include_router(eval_router)
    application.include_router(monitor_router)
    application.include_router(status_router)

    mount_spa(application)
    return application


app = _create_app()