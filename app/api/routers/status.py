"""状态与角色池路由：/api/status、/api/workers

契约：CONTRACT.md 第 2 节末尾。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.core.config import build_embeddings, load_config
from app.knowledge.rag import get_vectorstore
from app.orchestration.registry import WORKER_REGISTRY
from main import DB_PATH, PERSIST_DIR

router = APIRouter(tags=["status"])

# PERSIST_DIR 与 DB_PATH 与 main.py 保持一致（统一由 app.api 入口注入更稳，
# 但为减少对 main 模块的耦合，这里直接构造相同路径）。
from main import DB_PATH, PERSIST_DIR  # noqa: E402  -  延迟导入避免循环依赖

_REPORT_DIR = Path(__file__).resolve().parents[3] / "eval" / "reports"


@router.get("/api/workers")
def get_workers() -> list[dict[str, Any]]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "tool_names": list(spec.tool_names),
        }
        for spec in WORKER_REGISTRY
    ]


@router.get("/api/status")
def get_status() -> dict[str, Any]:
    cfg = load_config()
    kb_ready = (PERSIST_DIR / "chroma.sqlite3").exists()
    kb_chunks: int | None = None
    if kb_ready:
        try:
            embeddings = build_embeddings(cfg)
            vectorstore = get_vectorstore(PERSIST_DIR, embeddings)
            kb_chunks = len(vectorstore.get(include=[])["ids"])
        except Exception:  # noqa: BLE001 - 读取失败按不可用处理
            kb_chunks = None
    db_ready = DB_PATH.exists()
    reports_count = (
        len(list(_REPORT_DIR.glob("report_*.json"))) if _REPORT_DIR.exists() else 0
    )
    return {
        "provider": cfg.provider,
        "model": cfg.llm_model,
        "kb_ready": kb_ready,
        "db_ready": db_ready,
        "kb_chunks": kb_chunks,
        "reports_count": reports_count,
    }