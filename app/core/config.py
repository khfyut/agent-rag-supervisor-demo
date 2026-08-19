"""模型与运行配置：支持 openai / ollama（OpenAI 兼容端点）/ mock 三种 provider。"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _load_dotenv() -> None:
    """轻量加载项目根目录 .env 文件（不覆盖已存在的环境变量），避免额外依赖。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(root, ".env")
    if not os.path.exists(dotenv_path):
        return
    with open(dotenv_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


@dataclass
class ModelConfig:
    provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    supervisor_model: str | None = None
    worker_model: str | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    max_iterations: int = 4


def load_config(provider_override: str | None = None) -> ModelConfig:
    _load_dotenv()
    provider = (provider_override or os.getenv("LLM_PROVIDER", "openai")).strip().lower()
    embedding_provider = (os.getenv("EMBEDDING_PROVIDER") or "").strip().lower() or None
    cfg = ModelConfig(
        provider=provider,
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        supervisor_model=os.getenv("SUPERVISOR_MODEL"),
        worker_model=os.getenv("WORKER_MODEL"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        embedding_provider=embedding_provider,
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY"),
        max_iterations=int(os.getenv("MAX_ITERATIONS", "4")),
    )
    if provider == "ollama":
        cfg.llm_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        cfg.embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
        cfg.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        cfg.api_key = os.getenv("OLLAMA_API_KEY", "ollama")
        cfg.embedding_provider = embedding_provider or "ollama"
    elif provider == "deepseek":
        # DeepSeek 官方无 embedding API：chat 用 DeepSeek，embedding 默认走本地 Ollama
        cfg.llm_model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        cfg.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        cfg.api_key = os.getenv("DEEPSEEK_API_KEY")
        cfg.embedding_provider = embedding_provider or "ollama"
        if cfg.embedding_provider == "ollama":
            cfg.embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    elif provider == "minimax":
        # MiniMax 一个 key 全搞定：chat（MiniMax-Text-01）+ embedding（embo-01）
        cfg.llm_model = os.getenv("MINIMAX_MODEL", "MiniMax-Text-01")
        cfg.base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
        cfg.api_key = os.getenv("MINIMAX_API_KEY")
        cfg.embedding_provider = embedding_provider or "minimax"
        cfg.embedding_model = os.getenv("MINIMAX_EMBEDDING_MODEL", "embo-01")
    else:
        cfg.embedding_provider = embedding_provider or "openai"
    return cfg


def build_llm(cfg: ModelConfig, model: str | None = None):
    """根据配置构造聊天模型；model 参数可覆盖默认模型（用于分角色配置）。"""
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_openai import ChatOpenAI

    if cfg.provider == "mock":
        return FakeMessagesListChatModel(responses=[])
    return ChatOpenAI(
        model=model or cfg.llm_model,
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        temperature=0.2,
        request_timeout=120,
        max_tokens=4096,
    )


def build_embeddings(cfg: ModelConfig):
    """根据配置构造 embedding 模型。"""
    from langchain_core.embeddings import FakeEmbeddings
    from langchain_openai import OpenAIEmbeddings

    if cfg.provider == "mock" or cfg.embedding_provider == "mock":
        return FakeEmbeddings(size=384)
    ep = cfg.embedding_provider or cfg.provider
    if ep == "ollama":
        from .embeddings import OllamaEmbeddings

        return OllamaEmbeddings(
            model=cfg.embedding_model,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        )
    if ep == "minimax":
        from .embeddings import MiniMaxEmbeddings

        return MiniMaxEmbeddings(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            model=cfg.embedding_model,
        )
    # openai 走标准 OpenAI 兼容 /v1/embeddings
    return OpenAIEmbeddings(
        model=cfg.embedding_model,
        api_key=cfg.api_key,
        base_url=cfg.base_url,
    )
