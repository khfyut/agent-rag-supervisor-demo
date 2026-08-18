"""运行监测：进程内保存每次问答的完整 Agent 执行轨迹，供「数据监测」页查看。

数据只保存在内存（进程重启即清空），上限 50 条；不落盘，避免泄露 prompt / 数据。
"""

from __future__ import annotations

import threading
import time
from typing import Any

_MAX_RUNS = 50
_lock = threading.Lock()
_runs: dict[str, dict[str, Any]] = {}


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


def append_step(run_id: str, step: dict[str, Any]) -> None:
    with _lock:
        run = _runs.get(run_id)
        if run is not None:
            run["steps"].append(step)


def finish_run(run_id: str, **fields: Any) -> None:
    with _lock:
        run = _runs.get(run_id)
        if run is not None:
            run.update(fields)
            run["status"] = "done"


def fail_run(run_id: str, message: str) -> None:
    with _lock:
        run = _runs.get(run_id)
        if run is not None:
            run["status"] = "error"
            run["error"] = message


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
