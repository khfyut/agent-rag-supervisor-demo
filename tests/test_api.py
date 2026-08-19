"""后端 API 契约测试（CONTRACT.md 第 2、3 节）。

全程使用 mock provider（无需 API key）；知识库相关测试把 data/storage 目录
重定向到 pytest tmp_path，避免污染真实 data/kb 与 storage/chroma。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.knowledge import kb_service  # noqa: E402
from app.api import app  # noqa: E402

client = TestClient(app)


def parse_sse(text: str) -> list[tuple[str, dict]]:
    """解析 text/event-stream 响应为 [(event, data), ...]。"""
    events: list[tuple[str, dict]] = []
    for block in text.strip().split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = ""
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        if event and data_lines:
            events.append((event, json.loads("\n".join(data_lines))))
    return events


@pytest.fixture
def tmp_kb(monkeypatch, tmp_path):
    """把知识库读写/重建重定向到临时目录，并用 mock embedding（无网络）。"""
    data_dir = tmp_path / "kb"
    persist_dir = tmp_path / "chroma"
    data_dir.mkdir()
    (data_dir / "示例文档.md").write_text(
        "这是示例知识库文档。\n退款政策：已支付但未开始制作的订单，支付后 30 分钟内"
        "可申请全额退款，系统自动审核通过。\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(kb_service, "DATA_DIR", data_dir)
    monkeypatch.setattr(kb_service, "PERSIST_DIR", persist_dir)
    monkeypatch.setattr(kb_service, "_dirty", False)
    monkeypatch.setattr(kb_service, "_chunk_counts", {})
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    return data_dir, persist_dir


# ---------- 状态 / 角色池 ----------


def test_status_contract():
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) == {
        "provider",
        "model",
        "kb_ready",
        "db_ready",
        "kb_chunks",
        "reports_count",
    }
    assert isinstance(data["kb_ready"], bool)
    assert isinstance(data["db_ready"], bool)


def test_workers_contract():
    resp = client.get("/api/workers")
    assert resp.status_code == 200
    data = resp.json()
    assert [w["name"] for w in data] == [
        "rag_researcher",
        "sql_analyst",
        "web_searcher",
        "stock_analyst",
    ]
    for w in data:
        assert isinstance(w["description"], str)
        assert isinstance(w["tool_names"], list)
        assert all(isinstance(t, str) for t in w["tool_names"])


# ---------- 问答 /api/ask ----------


def test_ask_mock_event_sequence():
    resp = client.post(
        "/api/ask",
        json={"question": "已支付但未开始制作的订单多久内可以申请全额退款？", "provider": "mock"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(resp.text)
    types = [e[0] for e in events]
    # mock 剧本：run_start → supervisor → worker → supervisor → reviewer → supervisor → done
    assert types == [
        "run_start",
        "supervisor",
        "worker",
        "supervisor",
        "reviewer",
        "supervisor",
        "done",
    ]

    start = events[0][1]
    assert set(start) == {"run_id", "question"}
    assert start["question"] == "已支付但未开始制作的订单多久内可以申请全额退款？"

    worker = [e[1] for e in events if e[0] == "worker"][0]
    assert set(worker) == {
        "worker",
        "findings",
        "tool_calls",
        "self_check",
        "error",
    }

    done = events[-1][1]
    assert done["quality"] == "verified"
    assert done["finish_reason"] == "review_pass"
    assert done["final_answer"]
    assert done["trace"]
    assert done["iterations"] >= 1
    assert isinstance(done["findings"], list)
    assert done["emergency_report"] is None
    assert done["guardrail"] is None


def test_ask_invalid_provider_emits_error():
    resp = client.post("/api/ask", json={"question": "x", "provider": "bogus"})
    events = parse_sse(resp.text)
    assert events[-1][0] == "error"
    assert events[-1][1]["message"]


def test_ask_empty_question_returns_422():
    resp = client.post("/api/ask", json={"provider": "mock"})
    assert resp.status_code == 422


# ---------- 知识库 /api/kb/* ----------


def test_kb_docs_initial(tmp_kb):
    resp = client.get("/api/kb/docs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dirty"] is False
    names = [d["name"] for d in data["docs"]]
    assert "示例文档.md" in names
    for d in data["docs"]:
        assert set(d) == {"name", "size", "modified_at", "chunk_count"}


def test_kb_upload_delete(tmp_kb):
    # 上传合法文档
    resp = client.post(
        "/api/kb/docs",
        files={
            "file": (
                "新文档.md",
                "满减活动仅限实物商品。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["dirty"] is True
    assert "新文档.md" in [d["name"] for d in data["docs"]]

    # 预览
    resp = client.get("/api/kb/docs/新文档.md")
    assert resp.status_code == 200
    assert resp.json()["content"] == "满减活动仅限实物商品。"

    # 删除
    resp = client.delete("/api/kb/docs/新文档.md")
    assert resp.status_code == 200
    assert "新文档.md" not in [d["name"] for d in resp.json()["docs"]]

    # 删除不存在的文档 → 404
    assert client.delete("/api/kb/docs/不存在.md").status_code == 404


def test_kb_upload_validation(tmp_kb):
    # 坏扩展名
    resp = client.post(
        "/api/kb/docs",
        files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
    )
    assert resp.status_code == 400

    # 超 1MB
    resp = client.post(
        "/api/kb/docs",
        files={"file": ("big.md", b"x" * (1024 * 1024 + 1), "text/markdown")},
    )
    assert resp.status_code == 400

    # 路径穿越
    resp = client.post(
        "/api/kb/docs",
        files={"file": ("../evil.md", b"x", "text/markdown")},
    )
    assert resp.status_code == 400

    # 非 UTF-8 内容
    resp = client.post(
        "/api/kb/docs",
        files={"file": ("bad.md", b"\xff\xfe\x00\x01", "text/markdown")},
    )
    assert resp.status_code == 400


def test_kb_rebuild_sse_and_search(tmp_kb):
    resp = client.post("/api/kb/rebuild")
    assert resp.status_code == 200
    events = parse_sse(resp.text)
    types = [e[0] for e in events]
    assert types[0] == "kb_build_start"
    assert "kb_build_file" in types
    assert types[-1] == "kb_build_done"

    start = events[0][1]
    assert start == {"total_files": 1}
    file_events = [e[1] for e in events if e[0] == "kb_build_file"]
    assert len(file_events) == 1
    assert file_events[0]["filename"] == "示例文档.md"
    assert file_events[0]["chunks"] >= 1

    done = events[-1][1]
    assert done["total_docs"] == 1
    assert done["total_chunks"] >= 1
    assert done["collection_count"] == done["total_chunks"]

    # 重建后 dirty=false 且 chunk_count 已刷新
    data = client.get("/api/kb/docs").json()
    assert data["dirty"] is False
    doc = [d for d in data["docs"] if d["name"] == "示例文档.md"][0]
    assert doc["chunk_count"] == done["total_chunks"]

    # 检索测试台
    resp = client.post("/api/kb/search", json={"query": "退款政策", "k": 3})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert 0 < len(results) <= 3
    for r in results:
        assert set(r) == {"content", "source", "chunk_id", "score", "citation_valid"}
        assert isinstance(r["citation_valid"], bool)
        # 检索返回的引用必须能通过核验（元数据按 chunk_id 查询）
        assert r["citation_valid"] is True


def test_kb_search_validation(tmp_kb):
    resp = client.post("/api/kb/search", json={"query": "  ", "k": 4})
    assert resp.status_code == 400


# ---------- 评估 /api/eval/* ----------


def test_eval_reports_list():
    resp = client.get("/api/eval/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert "reports" in data
    for r in data["reports"]:
        assert set(r) == {
            "filename",
            "generated_at",
            "provider",
            "model",
            "total_cases",
            "task_success_rate",
            "reviewer_pass_rate",
            "avg_iterations",
            "avg_elapsed_s",
            "degradation_rate",
            "degradation_delivery_rate",
            "honest_failure_rate",
            "hallucination_blocked",
        }


def test_eval_report_detail_not_found():
    assert client.get("/api/eval/reports/不存在.json").status_code == 404


def test_eval_run_mock(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    resp = client.post(
        "/api/eval/run",
        json={"provider": "mock", "limit": 1, "max_iterations": 2},
    )
    assert resp.status_code == 200
    events = parse_sse(resp.text)
    types = [e[0] for e in events]
    assert types[0] == "eval_start"
    assert types[1] == "eval_case"
    assert types[-1] == "eval_done"

    start = events[0][1]
    assert start == {"total": 1}
    case = events[1][1]
    assert set(case) == {
        "index",
        "id",
        "level",
        "success",
        "missing_keywords",
    }
    done = events[-1][1]
    assert done["filename"].startswith("report_")
    assert done["report"]["total_cases"] == 1
    assert done["report"]["cases"][0]["id"] == case["id"]

    # 清理本次测试生成的报告文件
    report_path = ROOT / "eval" / "reports" / done["filename"]
    assert report_path.exists()
    report_path.unlink()


def test_eval_run_invalid_provider():
    resp = client.post("/api/eval/run", json={"provider": "bogus"})
    events = parse_sse(resp.text)
    assert events[-1][0] == "eval_error"


# ---------- 运行监测 /api/monitor/* ----------


def test_monitor_records_ask_run(tmp_kb):
    resp = client.post(
        "/api/ask",
        json={
            "question": "已支付但未开始制作的订单多久内可以申请全额退款？",
            "provider": "mock",
        },
    )
    assert resp.status_code == 200
    assert parse_sse(resp.text)[-1][0] == "done"

    runs = client.get("/api/monitor/runs").json()["runs"]
    assert runs, "monitor 应记录本次运行"
    latest = runs[0]
    assert latest["question"].startswith("已支付但未开始制作")
    assert latest["status"] == "done"

    detail = client.get(f"/api/monitor/runs/{latest['run_id']}").json()["run"]
    assert detail["status"] == "done"
    assert detail["final_answer"]
    nodes = [s["node"] for s in detail["steps"]]
    assert "supervisor" in nodes
    assert "worker" in nodes
    supervisor_step = next(s for s in detail["steps"] if s["node"] == "supervisor")
    assert "input" in supervisor_step
    assert "output" in supervisor_step
    worker_step = next(s for s in detail["steps"] if s["node"] == "worker")
    assert "tool_calls" in worker_step
    assert "findings" in worker_step
    assert "instructions" in worker_step
    assert "input" in worker_step
    assert "output" in worker_step
    assert isinstance(worker_step.get("log"), list)

    # 不存在的 run_id → 404
    assert client.get("/api/monitor/runs/not-exist").status_code == 404
