"""运行监测路由：/api/monitor/*

契约：CONTRACT.md 第 2 节末尾。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.observability import monitor

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


@router.get("/runs")
def monitor_runs() -> dict[str, Any]:
    return {"runs": monitor.list_runs()}


@router.get("/runs/{run_id}")
def monitor_run(run_id: str) -> dict[str, Any]:
    run = monitor.get_run(run_id)
    if run is None:
        raise HTTPException(404, f"运行记录不存在: {run_id}")
    return {"run": run}