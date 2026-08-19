"""运行监测：进程内保存每次问答的完整 Agent 执行轨迹,供"数据监测"页查看。

数据只保存在内存（进程重启即清空）,上限 50 条；不落盘,避免泄露 prompt / 数据。

可选:在 .env 配 LANGSMITH_API_KEY + LANGSMITH_TRACING=true 后,会把同一份
trace 同步推到 LangSmith UI（https://smith.langchain.com）,便于评审/答辩时
直接打开看完整图。未配置时本文件行为完全等同历史版本,无任何副作用。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_MAX_RUNS = 50
_lock = threading.Lock()
_runs: dict[str, dict[str, Any]] = {}

# ---- LangSmith \u53ef\u9009\u63a5\u5165 ----
# \u4ec5\u5f53 LANGSMITH_API_KEY \u4e14\u663e\u5f0f\u5f00\u542f trace \u65f6\u542f\u7528\uff1b\u542f\u7528\u662f\u8d34\u7247\u7684,\u4e0d\u542f\u7528\u5c31\u662f\u4e60\u60ef\u7684\u5185\u5b58\u7f13\u5b58\u3002
# Client \u8fde\u63a5\u5931\u8d25 / \u7f51\u7edc\u4e0d\u53ef\u7528 \u2192 \u53ea\u8bb0 logger.warning\uff0c\u4e1a\u52a1\u8c03\u7528\u5168\u90e8\u62a5\u544a\u4e3a\u672c\u5730\u8bb0\u5f55\u3002
_ls_enabled: bool | None = None
_ls_client: Any = None
_ls_root_runs: dict[str, Any] = {}


def _init_langsmith() -> bool:
    """\u8fdf\u5ef6\u521d\u59cb\u5316\uff1a\u7b2c\u4e00\u6b21\u8c03\u7528\u65f6\u624d\u8bfb env\u3001\u9020 Client\u3002\u907f\u514d import \u671f\u51b2\u7a81\u3002"""
    global _ls_enabled, _ls_client
    if _ls_enabled is not None:
        return _ls_enabled
    import os

    api_key = os.environ.get("LANGSMITH_API_KEY")
    tracing = (
        os.environ.get("LANGSMITH_TRACING", "").lower() in {"1", "true", "yes"}
        or os.environ.get("LANGCHAIN_TRACING_V2", "").lower() in {"1", "true", "yes"}
    )
    if not (api_key and tracing):
        _ls_enabled = False
        return False
    try:
        from langsmith import Client  # type: ignore

        _ls_client = Client()
        _ls_enabled = True
        logger.info(
            "LangSmith \u5df2\u542f\u7528\uff0ctrace \u4e0a\u4f20\u5230\u9879\u76ee %s",
            os.environ.get("LANGSMITH_PROJECT", "(default)"),
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("LangSmith \u4e0d\u53ef\u7528\uff0c\u4ec5\u672c\u5730\u8bb0\u5f55: %s", exc)
        _ls_enabled = False
        _ls_client = None
    return _ls_enabled


def start_run(run_id: str, question: str, provider: str | None) -> None:
    with _lock:
        _runs[run_id] = {
            "run_id": run_id,
            "question": question,
            "provider": provider or "",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "status": "running",
            "iterations": 0,
            "quality": "",
            "finish_reason": "",
            "final_answer": "",
            "error": "",
            "steps": [],
            "trace": [],
        }
        while len(_runs) > _MAX_RUNS:
            _runs.pop(next(iter(_runs)))
    if _init_langsmith() and _ls_client is not None:
        try:
            _ls_root_runs[run_id] = _ls_client.create_run(
                name=f"agent_run:{run_id[:8]}",
                inputs={"question": question, "provider": provider or ""},
                run_type="chain",
                start_time=time.time_ns(),
            )
        except Exception as exc:
            logger.warning("LangSmith start_run \u5931\u8d25: %s", exc)


def _ls_child(run_id: str, step: dict[str, Any]) -> None:
    """\u5728 start_run \u8bb0\u5f55\u7684\u6839 trace \u4e0b\u63a8\u4e00\u4e2a child span\u3002\u4e1a\u52a1\u5b9a\u4e49\u4e0d\u53d8:UI \u4e0a\u80fd\u770b\u5230\u6bcf\u4e2a LangGraph \u8282\u70b9\u3002"""
    parent = _ls_root_runs.get(run_id)
    if parent is None or _ls_client is None:
        return
    try:
        _ls_client.create_run(
            name=str(step.get("node") or step.get("event") or "step"),
            run_type="tool",
            inputs=step,
            parent_run_id=parent.id,
        )
    except Exception as exc:
        logger.warning("LangSmith append_step \u5931\u8d25: %s", exc)


def append_step(run_id: str, step: dict[str, Any]) -> None:
    with _lock:
        run = _runs.get(run_id)
        if run is not None:
            run["steps"].append(step)
    if _init_langsmith():
        _ls_child(run_id, step)


def finish_run(run_id: str, **fields: Any) -> None:
    with _lock:
        run = _runs.get(run_id)
        if run is not None:
            run.update(fields)
            run["status"] = "done"
    parent = _ls_root_runs.pop(run_id, None) if _init_langsmith() else None
    if parent is not None and _ls_client is not None:
        try:
            _ls_client.update_run(parent.id, outputs=fields, end_time=time.time_ns())
        except Exception as exc:
            logger.warning("LangSmith finish_run \u5931\u8d25: %s", exc)


def fail_run(run_id: str, message: str) -> None:
    with _lock:
        run = _runs.get(run_id)
        if run is not None:
            run["status"] = "error"
            run["error"] = message
    parent = _ls_root_runs.pop(run_id, None) if _init_langsmith() else None
    if parent is not None and _ls_client is not None:
        try:
            _ls_client.update_run(parent.id, error=message, end_time=time.time_ns())
        except Exception as exc:
            logger.warning("LangSmith fail_run \u5931\u8d25: %s", exc)


def list_runs() -> list[dict[str, Any]]:
    with _lock:
        return [
            {
                k: r[k]
                for k in (
                    "run_id",
                    "question",
                    "provider",
                    "created_at",
                    "status",
                    "iterations",
                    "quality",
                    "finish_reason",
                )
            }
            for r in reversed(list(_runs.values()))
        ]


def get_run(run_id: str) -> dict[str, Any] | None:
    with _lock:
        run = _runs.get(run_id)
        return dict(run) if run is not None else None