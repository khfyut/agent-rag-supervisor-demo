"""问答路由：POST /api/ask

契约：CONTRACT.md 第 2 节。
图执行通过 SSE 实时推送 supervisor / worker / emergency / reviewer / guardrail / done 事件。
"""

from __future__ import annotations

import queue
import uuid
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.schemas import AskBody
from app.api.sse import drain as _drain
from app.api.sse import normalize_provider, spawn as _spawn, sse_event as _sse
from app.core.config import load_config
from app.observability import monitor
from app.orchestration.graph import initial_state
from app.orchestration.registry import WORKER_REGISTRY

WORKER_NAMES = {spec.name for spec in WORKER_REGISTRY}

router = APIRouter(tags=["chat"])


# ---------- chat 专属工具 ----------


def _extract_tool_calls(messages: list) -> list[dict[str, Any]]:
    """从节点返回的 messages 中提取 AIMessage.tool_calls -> [{name, args}]。"""
    calls: list[dict[str, Any]] = []
    for msg in messages or []:
        for tc in getattr(msg, "tool_calls", None) or []:
            calls.append({"name": tc.get("name", ""), "args": tc.get("args", {})})
    return calls


def _extract_tool_activity(messages: list) -> list[dict[str, Any]]:
    """提取每次工具调用的名称、参数与返回结果（按 tool_call_id 与 ToolMessage 配对）。"""
    calls: list[dict[str, Any]] = []
    for msg in messages or []:
        for tc in getattr(msg, "tool_calls", None) or []:
            calls.append(
                {
                    "name": tc.get("name", ""),
                    "args": tc.get("args", {}),
                    "result": None,
                    "_tool_call_id": tc.get("id", ""),
                }
            )
    results: dict[str, str] = {}
    for msg in messages or []:
        tcid = getattr(msg, "tool_call_id", None)
        if tcid:
            content = msg.content
            results[tcid] = content if isinstance(content, str) else str(content)
    for call in calls:
        call["result"] = results.get(call.pop("_tool_call_id", ""), None)
    return calls


# ---------- chat 专属 worker ----------


def _ask_worker(
    question: str,
    provider: str | None,
    max_iterations: int | None,
    events: queue.Queue,
) -> None:
    """在子线程里跑 LangGraph 图，按节点把事件推到 SSE 队列。"""
    from main import build_runtime  # 延迟导入避免循环依赖

    cfg = load_config(provider)
    if max_iterations is not None:
        cfg.max_iterations = max_iterations
    run_id = uuid.uuid4().hex[:12]
    events.put(("run_start", {"run_id": run_id, "question": question}))
    monitor.start_run(run_id, question, provider)

    try:
        graph = build_runtime(cfg, question)
        state: dict[str, Any] = {}
        last_instructions = ""
        for update in graph.stream(initial_state(question), stream_mode="updates"):
            for node, data in update.items():
                for key, value in data.items():
                    if key == "trace":
                        state[key] = state.get(key, []) + list(value or [])
                    else:
                        state[key] = value
                if node == "supervisor":
                    entry = (data.get("trace") or [{}])[0]
                    decision = data.get("decision") or {}
                    dbg = data.get("debug") or {}
                    instructions = entry.get("instructions") or decision.get("instructions", "")
                    last_instructions = instructions
                    events.put(
                        (
                            "supervisor",
                            {
                                "iteration": entry.get("iteration", 0),
                                "next": entry.get("next") or decision.get("next", ""),
                                "instructions": instructions,
                            },
                        )
                    )
                    monitor.append_step(
                        run_id,
                        {
                            "node": "supervisor",
                            "iteration": entry.get("iteration", 0),
                            "next": entry.get("next") or decision.get("next", ""),
                            "instructions": instructions,
                            "input": dbg.get("input"),
                            "output": dbg.get("output"),
                        },
                    )
                elif node in WORKER_NAMES:
                    wr = data.get("worker_report") or {}
                    dbg = data.get("debug") or {}
                    events.put(
                        (
                            "worker",
                            {
                                "worker": node,
                                "findings": data.get("findings", []),
                                "tool_calls": _extract_tool_calls(data.get("messages", [])),
                                "self_check": wr.get("self_check", ""),
                                "error": wr.get("error", ""),
                            },
                        )
                    )
                    monitor.append_step(
                        run_id,
                        {
                            "node": "worker",
                            "worker": node,
                            "instructions": last_instructions,
                            "tool_calls": _extract_tool_activity(data.get("messages", [])),
                            "findings": data.get("findings", []),
                            "self_check": wr.get("self_check", ""),
                            "error": wr.get("error", ""),
                            "input": dbg.get("input"),
                            "output": dbg.get("output"),
                            "log": dbg.get("log") or [],
                        },
                    )
                elif node == "reviewer":
                    review = data.get("review") or {}
                    dbg = data.get("debug") or {}
                    events.put(
                        (
                            "reviewer",
                            {
                                "verdict": review.get("verdict", ""),
                                "feedback": review.get("feedback", ""),
                            },
                        )
                    )
                    monitor.append_step(
                        run_id,
                        {
                            "node": "reviewer",
                            "verdict": review.get("verdict", ""),
                            "feedback": review.get("feedback", ""),
                            "input": dbg.get("input"),
                            "output": dbg.get("output"),
                        },
                    )
                elif node == "emergency_synthesizer":
                    report = data.get("emergency_report") or {}
                    dbg = data.get("debug") or {}
                    events.put(
                        (
                            "emergency",
                            {
                                "report": report,
                                "confidence": report.get("confidence", 0.0),
                            },
                        )
                    )
                    monitor.append_step(
                        run_id,
                        {
                            "node": "emergency_synthesizer",
                            "report": report,
                            "confidence": report.get("confidence", 0.0),
                            "input": dbg.get("input"),
                            "output": dbg.get("output"),
                        },
                    )
                elif node == "guardrail":
                    g = data.get("guardrail") or {}
                    dbg = data.get("debug") or {}
                    events.put(
                        (
                            "guardrail",
                            {
                                "passed": bool(g.get("passed")),
                                "quality": g.get("quality", ""),
                                "reason": g.get("reason", ""),
                            },
                        )
                    )
                    monitor.append_step(
                        run_id,
                        {
                            "node": "guardrail",
                            "passed": bool(g.get("passed")),
                            "quality": g.get("quality", ""),
                            "reason": g.get("reason", ""),
                            "input": dbg.get("input"),
                            "output": dbg.get("output"),
                        },
                    )
    except Exception as exc:  # noqa: BLE001 - 记录失败原因后交给 spawn 统一发 error
        monitor.fail_run(run_id, f"{type(exc).__name__}: {exc}")
        raise

    monitor.finish_run(
        run_id,
        iterations=state.get("iterations", 0),
        quality=state.get("quality", ""),
        finish_reason=state.get("finish_reason", ""),
        final_answer=state.get("final_answer", ""),
        trace=state.get("trace", []),
    )
    events.put(
        (
            "done",
            {
                "final_answer": state.get("final_answer", ""),
                "quality": state.get("quality", ""),
                "finish_reason": state.get("finish_reason", ""),
                "iterations": state.get("iterations", 0),
                "trace": state.get("trace", []),
                "findings": state.get("findings", []),
                "analysis": state.get("analysis", []),
                "emergency_report": state.get("emergency_report"),
                "guardrail": state.get("guardrail"),
            },
        )
    )


# ---------- 路由 ----------


@router.post("/api/ask")
def ask(body: AskBody) -> StreamingResponse:
    try:
        provider = normalize_provider(body.provider)
    except ValueError as exc:
        return StreamingResponse(
            iter([_sse("error", {"message": str(exc)})]),
            media_type="text/event-stream",
        )
    events, thread = _spawn(
        _ask_worker, "error", body.question, provider, body.max_iterations
    )
    return StreamingResponse(
        _drain(events, thread, {"done", "error"}),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )