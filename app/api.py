"""FastAPI 服务层：问答 / 评估 / 知识库管理 HTTP + SSE 接口。

契约：CONTRACT.md 第 2、3 节。所有 SSE 统一为 text/event-stream，
事件帧 `event: <name>\\ndata: <json>\\n\\n`；出错时先发 *_error 事件再结束流。
"""

from __future__ import annotations

import asyncio
import json
import queue
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import kb_service, monitor  # noqa: E402
from app.config import build_embeddings, load_config  # noqa: E402
from app.graph import initial_state  # noqa: E402
from app.rag import get_vectorstore, search_knowledge, verify_citations  # noqa: E402
from app.registry import WORKER_REGISTRY  # noqa: E402
from main import DB_PATH, PERSIST_DIR, build_runtime  # noqa: E402

CASES_PATH = ROOT / "eval" / "cases.json"
REPORT_DIR = ROOT / "eval" / "reports"
WEB_DIST = ROOT / "web" / "dist"

ALLOWED_PROVIDERS = {"openai", "ollama", "deepseek", "minimax", "mock", None}
WORKER_NAMES = {spec.name for spec in WORKER_REGISTRY}

app = FastAPI(title="Multi-Agent RAG Supervisor API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- 请求体 ----------


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


# ---------- SSE 工具 ----------


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _normalize_provider(provider: str | None) -> str | None:
    provider = (provider or "").strip().lower() or None
    if provider not in ALLOWED_PROVIDERS:
        raise ValueError(
            f"不支持的 provider: {provider}（可选 openai|ollama|deepseek|minimax|mock）"
        )
    return provider


def _extract_tool_calls(messages: list) -> list[dict[str, Any]]:
    """从节点返回的 messages 中提取 AIMessage.tool_calls → [{name, args}]。"""
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


def _spawn(fn, error_event: str, *args):
    """把同步的图执行放进线程，通过队列向 SSE 流推送事件。"""
    events: queue.Queue[tuple[str, dict]] = queue.Queue()

    def target() -> None:
        try:
            fn(*args, events)
        except Exception as exc:  # noqa: BLE001 - 统一转成 *_error 事件
            events.put((error_event, {"message": f"{type(exc).__name__}: {exc}"}))

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return events, thread


async def _drain(
    events: queue.Queue, thread: threading.Thread, terminal: set[str]
) -> AsyncIterator[str]:
    """消费队列直到收到终止事件；线程异常退出时兜底发 error。"""
    while True:
        try:
            event, data = events.get_nowait()
            yield _sse(event, data)
            if event in terminal:
                return
        except queue.Empty:
            if not thread.is_alive():
                yield _sse("error", {"message": "服务内部错误：执行线程异常退出"})
                return
            await asyncio.sleep(0.05)


# ---------- 问答 /api/ask ----------


def _ask_worker(
    question: str,
    provider: str | None,
    max_iterations: int | None,
    events: queue.Queue,
) -> None:
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
    except Exception as exc:  # noqa: BLE001 - 记录失败原因后交给 _spawn 统一发 error
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


@app.post("/api/ask")
def ask(body: AskBody) -> StreamingResponse:
    try:
        provider = _normalize_provider(body.provider)
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


# ---------- 知识库 /api/kb/* ----------


@app.get("/api/kb/docs")
def kb_docs() -> dict[str, Any]:
    return {"docs": kb_service.list_docs(), "dirty": kb_service.is_dirty()}


@app.get("/api/kb/docs/{filename}")
def kb_doc(filename: str) -> dict[str, Any]:
    try:
        return kb_service.read_doc(filename)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/kb/docs")
async def kb_upload(file: UploadFile = File(...)) -> dict[str, Any]:
    content = await file.read()
    try:
        return kb_service.save_upload(file.filename or "", content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/kb/docs/{filename}")
def kb_delete(filename: str) -> dict[str, Any]:
    try:
        return kb_service.delete_doc(filename)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _rebuild_worker(events: queue.Queue) -> None:
    files = kb_service.list_kb_files()
    total = len(files)
    events.put(("kb_build_start", {"total_files": total}))

    def on_progress(current: int, total_files: int, filename: str, chunks: int) -> None:
        events.put(
            (
                "kb_build_file",
                {
                    "current": current,
                    "total": total_files,
                    "filename": filename,
                    "chunks": chunks,
                },
            )
        )

    result = kb_service.rebuild(on_progress)
    events.put(("kb_build_done", result))


@app.post("/api/kb/rebuild")
def kb_rebuild() -> StreamingResponse:
    events, thread = _spawn(_rebuild_worker, "kb_build_error")
    return StreamingResponse(
        _drain(events, thread, {"kb_build_done", "kb_build_error", "error"}),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/kb/search")
def kb_search(body: SearchBody) -> dict[str, Any]:
    query = (body.query or "").strip()
    if not query:
        raise HTTPException(400, "query 不能为空")
    k = max(1, min(8, body.k or 4))
    try:
        cfg = load_config()
        embeddings = build_embeddings(cfg)
        vectorstore = get_vectorstore(kb_service.PERSIST_DIR, embeddings)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"向量库不可用: {exc}") from exc
    results = search_knowledge(vectorstore, query, k=k)
    ids = [r.get("chunk_id") or "" for r in results]
    verdict = verify_citations(vectorstore, ids)
    valid = set(verdict["valid"])
    for r in results:
        r["citation_valid"] = (r.get("chunk_id") or "") in valid
    return {"results": results}


# ---------- 评估 /api/eval/* ----------


def _eval_worker(
    provider: str | None,
    limit: int | None,
    max_iterations: int | None,
    events: queue.Queue,
) -> None:
    from eval.evaluate import _process_metrics, _tool_accuracy, _write_report

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


@app.post("/api/eval/run")
def eval_run(body: EvalRunBody) -> StreamingResponse:
    try:
        provider = _normalize_provider(body.provider)
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


@app.get("/api/eval/reports")
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


@app.get("/api/eval/reports/{filename}")
def eval_report(filename: str) -> dict[str, Any]:
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(404, "报告不存在")
    path = REPORT_DIR / filename
    if not path.is_file():
        raise HTTPException(404, f"报告不存在: {filename}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["filename"] = path.name
    return data


# ---------- 运行监测 /api/monitor/* ----------


@app.get("/api/monitor/runs")
def monitor_runs() -> dict[str, Any]:
    return {"runs": monitor.list_runs()}


@app.get("/api/monitor/runs/{run_id}")
def monitor_run(run_id: str) -> dict[str, Any]:
    run = monitor.get_run(run_id)
    if run is None:
        raise HTTPException(404, f"运行记录不存在: {run_id}")
    return {"run": run}


# ---------- 状态 / 角色池 ----------


@app.get("/api/workers")
def get_workers() -> list[dict[str, Any]]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "tool_names": list(spec.tool_names),
        }
        for spec in WORKER_REGISTRY
    ]


@app.get("/api/status")
def get_status() -> dict[str, Any]:
    cfg = load_config()
    kb_ready = (PERSIST_DIR / "chroma.sqlite3").exists()
    kb_chunks: int | None = None
    if kb_ready:
        try:
            embeddings = build_embeddings(cfg)
            vectorstore = get_vectorstore(PERSIST_DIR, embeddings)
            kb_chunks = len(vectorstore.get(include=[])["ids"])
        except Exception:  # noqa: BLE001 - 读取失败按不可用处理
            kb_chunks = None
    db_ready = DB_PATH.exists()
    reports_count = (
        len(list(REPORT_DIR.glob("report_*.json"))) if REPORT_DIR.exists() else 0
    )
    return {
        "provider": cfg.provider,
        "model": cfg.llm_model,
        "kb_ready": kb_ready,
        "db_ready": db_ready,
        "kb_chunks": kb_chunks,
        "reports_count": reports_count,
    }


# ---------- 生产模式静态托管（web/dist） ----------

if WEB_DIST.exists():
    assets_dir = WEB_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        target = (WEB_DIST / full_path).resolve()
        if (
            full_path
            and target.is_file()
            and str(target).startswith(str(WEB_DIST.resolve()))
        ):
            return FileResponse(target)
        # index.html 禁止缓存：内容哈希变化的 JS/CSS 由 /assets 提供，
        # 若 HTML 被缓存，重建后浏览器会请求已不存在的旧资源而白屏。
        return FileResponse(
            WEB_DIST / "index.html",
            headers={"Cache-Control": "no-cache"},
        )
