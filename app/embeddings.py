"""原生 Embedding 适配器：MiniMax / Ollama。

MiniMax 的 /v1/embeddings 与 OpenAI 格式不兼容：
请求参数是 texts + type（query/db），响应是 vectors 而不是 data。
Ollama 的 /v1/embeddings 兼容 OpenAI 格式，但 langchain 的 OpenAIEmbeddings
会携带 Ollama 不认识的参数，因此统一用原生适配器。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from langchain_core.embeddings import Embeddings


class MiniMaxEmbeddings(Embeddings):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "embo-01",
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _embed(self, texts: list[str], type_: str) -> list[list[float]]:
        body = json.dumps(
            {"model": self.model, "texts": texts, "type": type_}
        ).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/embeddings",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"MiniMax embedding HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:200]}"
            ) from exc
        vectors = data.get("vectors")
        if not vectors:
            resp = data.get("base_resp", {})
            raise RuntimeError(
                f"MiniMax embedding 失败: {resp.get('status_code')} {resp.get('status_msg')}"
            )
        return [list(v) for v in vectors]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "db")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "query")[0]


class OllamaEmbeddings(Embeddings):
    """Ollama OpenAI 兼容 /v1/embeddings 适配器。"""

    def __init__(
        self,
        base_url: str,
        model: str = "nomic-embed-text",
        timeout: int = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _embed(self, texts: list[str]) -> list[list[float]]:
        body = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/embeddings",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Ollama embedding HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:200]}"
            ) from exc
        items = data.get("data") or []
        if not items:
            raise RuntimeError(f"Ollama embedding 无返回数据: {str(data)[:200]}")
        return [list(item["embedding"]) for item in items]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]
