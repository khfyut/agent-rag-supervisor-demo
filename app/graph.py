"""LangGraph 图组装：Supervisor 模式 + 角色池动态选择（手写条件路由，展示原理）。"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph

from .agents import (
    make_emergency_synthesizer_node,
    make_reviewer_node,
    make_supervisor_node,
    make_worker_node,
)
from .guardrail import make_guardrail_node
from .registry import WORKER_REGISTRY
from .state import AgentState


def _route(state: AgentState) -> str:
    return state["decision"]["next"]


def build_graph(
    models: dict[str, BaseChatModel],
    tools: dict[str, BaseTool],
    max_iterations: int = 4,
    include_reviewer: bool = True,
    include_guardrail: bool = True,
):
    """models: {"supervisor": ..., "reviewer": ..., <worker_name>: ...}；tools: {"tool_name": tool}

    include_reviewer / include_guardrail 用于消融实验（第 7 章 7.4）：
    关掉对应组件后跑同一评估集，对比分数即可定位组件贡献。
    """
    builder = StateGraph(AgentState)
    builder.add_node(
        "supervisor",
        make_supervisor_node(models["supervisor"], max_iterations),
    )
    route_map: dict[str, str] = {"finish": END}
    route_map["reviewer"] = "reviewer" if include_reviewer else END
    route_map["emergency"] = "emergency_synthesizer" if include_guardrail else END
    for spec in WORKER_REGISTRY:
        worker_tools = [tools[name] for name in spec.tool_names]
        model = models.get(spec.name) or models.get("worker") or models["supervisor"]
        builder.add_node(
            spec.name,
            make_worker_node(model, worker_tools, spec.system_prompt, "findings"),
        )
        builder.add_edge(spec.name, "supervisor")
        route_map[spec.name] = spec.name
    if include_reviewer:
        builder.add_node("reviewer", make_reviewer_node(models["reviewer"]))
    if include_guardrail:
        builder.add_node(
            "emergency_synthesizer",
            make_emergency_synthesizer_node(
                models.get("emergency_synthesizer") or models.get("worker") or models["supervisor"]
            ),
        )
        builder.add_node("guardrail", make_guardrail_node())

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges("supervisor", _route, route_map)
    # 关键：Worker（角色池中的专家）与 Reviewer 都回到 Supervisor —— 构成自主循环，而不是流水线
    if include_reviewer:
        builder.add_edge("reviewer", "supervisor")
    if include_guardrail:
        # 降级路径：紧急综合 → 规则门控 → 结束（不再回到 Supervisor）
        builder.add_edge("emergency_synthesizer", "guardrail")
        builder.add_edge("guardrail", END)
    return builder.compile()


def initial_state(question: str) -> dict[str, Any]:
    from langchain_core.messages import HumanMessage

    return {
        "question": question,
        "messages": [HumanMessage(content=question)],
        "decision": {},
        "findings": [],
        "analysis": [],
        "draft": "",
        "review": None,
        "feedback": [],
        "trace": [],
        "iterations": 0,
        "final_answer": "",
        "quality": "",
        "finish_reason": "",
        "emergency_report": None,
        "guardrail": None,
        "task_instructions": "",
        "worker_report": {},
    }
