"""知识库路由：/api/kb/*

契约：CONTRACT.md 第 2 节。
rebuild 走 SSE 推送 kb_build_* 事件；其余为常规 HTTP。
"""

from __future__ import annotations

import queue
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.api.schemas import SearchBody
from app.api.sse import drain as _drain
from app.api.sse import spawn as _spawn, sse_event as _sse
from app.core.config import build_embeddings, load_config
from app.knowledge import kb_service
from app.knowledge.rag import get_vectorstore, search_knowledge, verify_citations

router = APIRouter(prefix="/api/kb", tags=["kb"])


# ---------- rebuild worker ----------


def _rebuild_worker(events: queue.Queue) -> None:
    files = kb_service.list_kb_files()
    total = len(files)
    events.put(("kb_build_start", {"total_files": total}))

    def on_progress(current: int, total_files: int, filename: str, chunks: int) -> None:
        events.put(
            (
                "kb_build_file",
                {
                    "current": current,
                    "total": total_files,
                    "filename": filename,
                    "chunks": chunks,
                },
            )
        )

    result = kb_service.rebuild(on_progress)
    events.put(("kb_build_done", result))


# ---------- 路由 ----------


@router.get("/docs")
def kb_docs() -> dict[str, Any]:
    return {"docs": kb_service.list_docs(), "dirty": kb_service.is_dirty()}


@router.get("/docs/{filename}")
def kb_doc(filename: str) -> dict[str, Any]:
    try:
        return kb_service.read_doc(filename)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/docs")
async def kb_upload(file: UploadFile = File(...)) -> dict[str, Any]:
    content = await file.read()
    try:
        return kb_service.save_upload(file.filename or "", content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/docs/{filename}")
def kb_delete(filename: str) -> dict[str, Any]:
    try:
        return kb_service.delete_doc(filename)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/rebuild")
def kb_rebuild() -> StreamingResponse:
    events, thread = _spawn(_rebuild_worker, "kb_build_error")
    return StreamingResponse(
        _drain(events, thread, {"kb_build_done", "kb_build_error", "error"}),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/search")
def kb_search(body: SearchBody) -> dict[str, Any]:
    query = (body.query or "").strip()
    if not query:
        raise HTTPException(400, "query 不能为空")
    k = max(1, min(8, body.k or 4))
    try:
        cfg = load_config()
        embeddings = build_embeddings(cfg)
        vectorstore = get_vectorstore(kb_service.PERSIST_DIR, embeddings)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"向量库不可用: {exc}") from exc
    results = search_knowledge(vectorstore, query, k=k)
    ids = [r.get("chunk_id") or "" for r in results]
    verdict = verify_citations(vectorstore, ids)
    valid = set(verdict["valid"])
    for r in results:
        r["citation_valid"] = (r.get("chunk_id") or "") in valid
    return {"results": results}