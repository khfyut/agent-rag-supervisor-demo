"""评估路由：/api/eval/*

契约：CONTRACT.md 第 3 节。
run 走 SSE 推送 eval_* 事件；reports 为常规 HTTP。
"""

from __future__ import annotations

import json
import queue
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.schemas import EvalRunBody
from app.api.sse import drain as _drain
from app.api.sse import normalize_provider, spawn as _spawn, sse_event as _sse
from app.core.config import load_config
from app.orchestration.graph import initial_state

ROOT = Path(__file__).resolve().parents[3]
CASES_PATH = ROOT / "eval" / "cases.json"
REPORT_DIR = ROOT / "eval" / "reports"

router = APIRouter(prefix="/api/eval", tags=["eval"])


# ---------- eval worker ----------


def _eval_worker(
    provider: str | None,
    limit: int | None,
    max_iterations: int | None,
    events: "queue.Queue",
) -> None:
    from main import build_runtime  # 延迟导入避免循环依赖
    from eval.evaluate import _process_metrics, _tool_accuracy, _write_report  # noqa: E402

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if limit is not None and limit > 0:
        cases = cases[:limit]
    total = len(cases)
    events.put(("eval_start", {"total": total}))

    cfg = load_config(provider)
    if max_iterations is not None:
        cfg.max_iterations = max_iterations

    results = []
    for idx, case in enumerate(cases):
        graph = build_runtime(cfg, question=case["question"])
        start = time.time()
        result = graph.invoke(initial_state(case["question"]))
        elapsed = round(time.time() - start, 2)
        answer = result.get("final_answer") or ""
        keywords_hit = [k for k in case["required_keywords"] if k in answer]
        success = len(keywords_hit) == len(case["required_keywords"])
        proc = _process_metrics(result)
        reviewer_entries = [
            t for t in result.get("trace", []) if t.get("node") == "reviewer"
        ]
        guardrail = result.get("guardrail") or {}
        chunk_ids = [
            item.get("chunk_id")
            for item in (result.get("findings") or []) + (result.get("analysis") or [])
            if item.get("chunk_id")
        ]
        entry = {
            "id": case["id"],
            "type": case.get("type", "normal"),
            "level": case["level"],
            "success": success,
            "keywords_hit": keywords_hit,
            "missing_keywords": [
                k for k in case["required_keywords"] if k not in answer
            ],
            "tool_accurate": _tool_accuracy(result, case.get("expected_workers", [])),
            "iterations": result.get("iterations", 0),
            "tool_calls": proc["tool_calls"],
            "tokens": proc["tokens"],
            "elapsed_s": elapsed,
            "citations": chunk_ids,
            "citation_valid": len(chunk_ids) > 0,
            "reviewer_verdicts": [t.get("verdict") for t in reviewer_entries],
            "final_answer": answer[:200],
            "quality": result.get("quality", ""),
            "finish_reason": result.get("finish_reason", ""),
            "guardrail_reason": guardrail.get("reason", ""),
            "trace": result.get("trace", []),
        }
        results.append(entry)
        events.put(
            (
                "eval_case",
                {
                    "index": idx,
                    "id": case["id"],
                    "level": case["level"],
                    "success": success,
                    "missing_keywords": entry["missing_keywords"],
                },
            )
        )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = REPORT_DIR / f"report_{tag}.json"
    report = _write_report(cfg, results, False, out_path)
    report["filename"] = out_path.name
    events.put(("eval_done", {"report": report, "filename": out_path.name}))


# ---------- 路由 ----------


@router.post("/run")
def eval_run(body: EvalRunBody) -> StreamingResponse:
    try:
        provider = normalize_provider(body.provider)
    except ValueError as exc:
        return StreamingResponse(
            iter([_sse("eval_error", {"message": str(exc)})]),
            media_type="text/event-stream",
        )
    events, thread = _spawn(
        _eval_worker, "eval_error", provider, body.limit, body.max_iterations
    )
    return StreamingResponse(
        _drain(events, thread, {"eval_done", "eval_error", "error"}),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/reports")
def eval_reports() -> dict[str, Any]:
    if not REPORT_DIR.exists():
        return {"reports": []}
    metas = []
    for path in sorted(REPORT_DIR.glob("report_*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - 跳过损坏的报告
            continue
        metas.append(
            {
                "filename": path.name,
                "generated_at": data.get("generated_at", ""),
                "provider": data.get("provider", ""),
                "model": data.get("model", ""),
                "total_cases": data.get("total_cases", 0),
                "task_success_rate": data.get("task_success_rate", 0),
                "reviewer_pass_rate": data.get("reviewer_pass_rate", 0),
                "avg_iterations": data.get("avg_iterations", 0),
                "avg_elapsed_s": data.get("avg_elapsed_s", 0),
                "degradation_rate": data.get("degradation_rate", 0),
                "degradation_delivery_rate": data.get(
                    "degradation_delivery_rate", 0
                ),
                "honest_failure_rate": data.get("honest_failure_rate", 0),
                "hallucination_blocked": data.get("hallucination_blocked", 0),
            }
        )
    return {"reports": metas}


@router.get("/reports/{filename}")
def eval_report(filename: str) -> dict[str, Any]:
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(404, "报告不存在")
    path = REPORT_DIR / filename
    if not path.is_file():
        raise HTTPException(404, f"报告不存在: {filename}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["filename"] = path.name
    return data