"""LangGraph 共享状态定义。"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    question: str
    messages: Annotated[list[AnyMessage], add_messages]
    decision: dict[str, Any]
    findings: list[dict[str, Any]]
    analysis: list[dict[str, Any]]
    draft: str
    review: dict[str, Any] | None
    feedback: list[str]
    trace: Annotated[list[dict[str, Any]], operator.add]
    iterations: int
    final_answer: str
    quality: str
    finish_reason: str
    emergency_report: dict[str, Any] | None
    guardrail: dict[str, Any] | None
    task_instructions: str
    worker_report: dict[str, Any]
    debug: dict[str, Any]
