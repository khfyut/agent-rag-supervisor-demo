"""知识库文档管理服务：扫描 / 上传 / 删除 / 重建编排 / 分片统计。

契约：CONTRACT.md 第 2 节。文件规则：仅 .md / .txt、单文件 ≤1MB、
文件名只取 basename、服务端做路径穿越校验；上传/删除后 dirty=true，
重建成功后才置回 false（进程内状态即可）。
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable

from .config import build_embeddings, load_config
from .rag import build_kb

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "kb"
PERSIST_DIR = ROOT / "storage" / "chroma"

ALLOWED_EXTENSIONS = {".md", ".txt"}
MAX_FILE_SIZE = 1024 * 1024  # 1MB

_rebuild_lock = threading.Lock()
_dirty = False
_chunk_counts: dict[str, int] = {}


def _safe_name(name: str) -> str:
    """校验文件名：只接受 basename + 白名单扩展名，拒绝路径穿越。"""
    if not name or name != Path(name).name:
        raise ValueError("文件名不能包含路径")
    if ".." in name or any(ch in name for ch in "/\\"):
        raise ValueError("文件名非法（拒绝路径穿越）")
    if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("仅支持 .md / .txt 文档")
    return name


def list_kb_files() -> list[Path]:
    """顶层扫描 .md/.txt，顺序与 rag.load_documents 一致（md 在前、txt 在后，各自排序）。"""
    return sorted(DATA_DIR.glob("*.md")) + sorted(DATA_DIR.glob("*.txt"))


def list_docs() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in list_kb_files():
        stats = path.stat()
        docs.append(
            {
                "name": path.name,
                "size": stats.st_size,
                "modified_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.localtime(stats.st_mtime)
                ),
                "chunk_count": _chunk_counts.get(path.name),
            }
        )
    return docs


def read_doc(name: str) -> dict[str, Any]:
    """读取文档原文（Markdown 预览用）。"""
    _safe_name(name)
    path = DATA_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"文档不存在: {name}")
    return {"name": name, "content": path.read_text(encoding="utf-8")}


def save_upload(name: str, content: bytes) -> dict[str, Any]:
    """保存上传文档；返回最新 {docs, dirty}。同名文件直接覆盖。"""
    global _dirty
    _safe_name(name)
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("单文件不能超过 1MB")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("仅支持 UTF-8 编码文本") from exc
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / name).write_text(text, encoding="utf-8")
    _dirty = True
    _chunk_counts.pop(name, None)
    return {"docs": list_docs(), "dirty": _dirty}


def delete_doc(name: str) -> dict[str, Any]:
    """删除文档；返回最新 {docs, dirty}。"""
    global _dirty
    _safe_name(name)
    path = DATA_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"文档不存在: {name}")
    path.unlink()
    _dirty = True
    _chunk_counts.pop(name, None)
    return {"docs": list_docs(), "dirty": _dirty}


def is_dirty() -> bool:
    return _dirty


def _collection_chunk_counts(vectorstore) -> dict[str, int]:
    """按 source 元数据从向量库统计每个文件的分片数。"""
    counts: dict[str, int] = {}
    for path in list_kb_files():
        got = vectorstore.get(where={"source": path.name}, include=[])
        counts[path.name] = len(got.get("ids") or [])
    return counts


def rebuild(
    progress: Callable[[int, int, str, int], None] | None = None,
) -> dict[str, Any]:
    """全量重建向量库（与 CLI build-kb 行为一致：清空 collection 后重排）。

    返回 {total_docs, total_chunks, collection_count}；成功后 dirty=false。
    """
    global _dirty, _chunk_counts
    with _rebuild_lock:
        cfg = load_config()
        embeddings = build_embeddings(cfg)
        vectorstore = build_kb(DATA_DIR, PERSIST_DIR, embeddings, progress=progress)
        total_docs = len(list_kb_files())
        total_chunks = len(vectorstore.get(include=[])["ids"])
        _chunk_counts = _collection_chunk_counts(vectorstore)
        _dirty = False
        return {
            "total_docs": total_docs,
            "total_chunks": total_chunks,
            "collection_count": total_chunks,
        }
