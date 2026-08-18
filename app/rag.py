"""RAG 模块：知识库构建、向量检索、引用核验。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

COLLECTION_NAME = "knowledge"


def load_documents(data_dir: Path) -> list[Document]:
    """加载 data_dir 下的 .md / .txt 文件为 Document。"""
    docs: list[Document] = []
    files = sorted(data_dir.rglob("*.md")) + sorted(data_dir.rglob("*.txt"))
    for path in files:
        text = path.read_text(encoding="utf-8")
        docs.append(Document(page_content=text, metadata={"source": path.name}))
    return docs


def build_kb(
    data_dir: Path,
    persist_dir: Path,
    embeddings: Embeddings,
    chunk_size: int = 500,
    chunk_overlap: int = 80,
    progress: Callable[[int, int, str, int], None] | None = None,
) -> Chroma:
    """切块 + 向量化 + 写入 ChromaDB（先清空同名 collection，保证可重复构建）。

    progress(current, total, filename, chunks)：每处理完一个文件回调一次，
    chunks 为该文件产出的分片数；默认 None（CLI / 原有调用行为不变）。
    """
    import chromadb

    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_dir))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    docs = load_documents(data_dir)
    chunks: list[Document] = []
    total = len(docs)
    for i, doc in enumerate(docs, start=1):
        per_doc = splitter.split_documents([doc])
        chunks.extend(per_doc)
        if progress is not None:
            progress(i, total, doc.metadata.get("source", ""), len(per_doc))
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = f"{chunk.metadata['source']}#{i}"

    if not chunks:
        # 空知识库：仅确保 collection 存在，避免 from_documents 空列表报错
        client.get_or_create_collection(COLLECTION_NAME)
        return Chroma(
            persist_directory=str(persist_dir),
            embedding_function=embeddings,
            collection_name=COLLECTION_NAME,
        )

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(persist_dir),
        collection_name=COLLECTION_NAME,
    )
    return vectorstore


def get_vectorstore(persist_dir: Path, embeddings: Embeddings) -> Chroma:
    """加载已构建的向量库。"""
    return Chroma(
        persist_directory=str(persist_dir),
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
    )


def search_knowledge(vectorstore: Chroma, query: str, k: int = 4) -> list[dict[str, Any]]:
    """向量检索，返回带引用元数据（source / chunk_id）的结果。"""
    results = vectorstore.similarity_search_with_score(query, k=k)
    return [
        {
            "content": doc.page_content,
            "source": doc.metadata.get("source"),
            "chunk_id": doc.metadata.get("chunk_id"),
            "score": round(float(score), 4),
        }
        for doc, score in results
    ]


def verify_citations(vectorstore: Chroma, chunk_ids: list[str]) -> dict[str, Any]:
    """按元数据 chunk_id 从向量库核验引用是否真实存在。

    注意：Chroma 内部 id 是自动生成的 UUID，与 chunk_id 元数据不同，
    因此这里按 `where={"chunk_id": {"$in": [...]}}` 查询，而不是 ids。
    """
    ids = [cid for cid in chunk_ids if cid]
    if not ids:
        return {"valid": [], "missing": [], "total": 0}
    got = vectorstore.get(where={"chunk_id": {"$in": ids}})
    found = set()
    for meta in got.get("metadatas") or []:
        cid = (meta or {}).get("chunk_id")
        if cid:
            found.add(cid)
    valid = [cid for cid in ids if cid in found]
    missing = [cid for cid in ids if cid not in found]
    return {"valid": valid, "missing": missing, "total": len(ids)}
