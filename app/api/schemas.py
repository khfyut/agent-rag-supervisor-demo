"""请求/响应 Pydantic 模型。"""

from __future__ import annotations

from pydantic import BaseModel


class AskBody(BaseModel):
    question: str
    provider: str | None = None
    max_iterations: int | None = None


class EvalRunBody(BaseModel):
    provider: str | None = None
    limit: int | None = None
    max_iterations: int | None = None


class SearchBody(BaseModel):
    query: str
    k: int = 4