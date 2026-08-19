"""生产模式静态文件托管（SPA fallback）。

仅当 ``web/dist`` 构建产物存在时挂载；否则跳过，
开发期请直接由 Vite (http://localhost:5173) 服务前端。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[3]
WEB_DIST = ROOT / "web" / "dist"


def mount_spa(app: FastAPI) -> None:
    if not WEB_DIST.exists():
        return

    assets_dir = WEB_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        target = (WEB_DIST / full_path).resolve()
        if (
            full_path
            and target.is_file()
            and str(target).startswith(str(WEB_DIST.resolve()))
        ):
            return FileResponse(target)
        # index.html 禁止缓存：内容哈希变化的 JS/CSS 由 /assets 提供，
        # 若 HTML 被缓存，重建后浏览器会请求已不存在的旧资源而白屏。
        return FileResponse(
            WEB_DIST / "index.html",
            headers={"Cache-Control": "no-cache"},
        )