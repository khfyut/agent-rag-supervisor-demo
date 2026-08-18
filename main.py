"""CLI 入口：构建知识库、提问、mock 演示。"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402

from app.config import build_embeddings, build_llm, load_config  # noqa: E402
from app.graph import build_graph, initial_state  # noqa: E402
from app.rag import build_kb, get_vectorstore  # noqa: E402
from app.tools import make_tools  # noqa: E402

DATA_DIR = ROOT / "data" / "kb"
PERSIST_DIR = ROOT / "storage" / "chroma"
DB_PATH = ROOT / "data" / "db" / "orders.db"


class _ScriptedChatModel(FakeMessagesListChatModel):
    """mock 专用：假装支持 bind_tools，让 create_react_agent 可以构建；输出仍按剧本返回。"""

    is_scripted: bool = True

    def bind_tools(self, tools, **kwargs):
        return self


def build_mock_models(question: str) -> dict:
    """无 key 演示用的剧本化模型：Supervisor 按问题类型从角色池中选择专家。"""
    if any(k in question for k in ("多少", "退款率", "销量", "GMV", "统计", "金额", "几笔", "趋势")):
        worker = "sql_analyst"
        findings = [
            {"summary": "2026年第一季度共 9 笔订单，其中 1 笔已退款，退款率约 11%", "chunk_id": ""}
        ]
    elif any(k in question for k in ("库存", "缺货", "补货", "安全库存")):
        worker = "stock_analyst"
        findings = [
            {"summary": "库存低于安全库存的商品共 3 个 SKU，其中 1 个已缺货", "chunk_id": ""}
        ]
    elif any(k in question for k in ("外部", "最新", "新闻", "网上", "行业")):
        worker = "web_searcher"
        findings = [
            {"summary": "外部搜索结果：行业报告显示 2026 年茶饮行业趋势是数字化运营与健康化新品", "chunk_id": "", "source": "web"}
        ]
    else:
        worker = "rag_researcher"
        findings = [
            {
                "summary": "已支付但未开始制作的订单，可在支付后 30 分钟内申请全额退款，系统自动审核通过",
                "chunk_id": "平台合作规则.md#1",
                "source": "平台合作规则.md",
            }
        ]
    worker_script = json.dumps(
        {"findings": findings, "self_check": "ok", "error": "", "next_suggestion": ""},
        ensure_ascii=False,
    )
    supervisor_script = [
        json.dumps({"next": worker, "instructions": f"调用 {worker} 处理用户问题"}, ensure_ascii=False),
        json.dumps(
            {
                "next": "reviewer",
                "instructions": "对草稿报告做质检",
                "draft": "【草稿】2026年第一季度共 9 笔订单，其中 1 笔已退款，退款率约 11%。",
            },
            ensure_ascii=False,
        ),
        '{"next": "finish", "final_answer": null}',
    ]
    reviewer_script = [
        '{"verdict": "pass", "feedback": "", '
        '"revised_report": "2026年第一季度共 9 笔订单，其中 1 笔已退款，退款率约 11%。"}'
    ]
    if worker == "rag_researcher":
        emergency_report = {
            "summary": "已确认已支付未开始制作的订单可在 30 分钟内申请全额退款",
            "confirmed_facts": [
                {
                    "statement": "已支付未开始制作的订单可在支付后 30 分钟内申请全额退款",
                    "chunk_id": "平台合作规则.md#1",
                }
            ],
            "insights": ["根据现有数据推测，未制作订单的退款政策对顾客较为友好"],
            "to_verify": ["退款到账时间是否因支付渠道而异"],
            "confidence": 0.6,
        }
    else:
        emergency_report = {
            "summary": "2026年第一季度共 9 笔订单，退款率约 11%",
            "confirmed_facts": [
                {"statement": "2026年第一季度共 9 笔订单，其中 1 笔已退款", "chunk_id": ""}
            ],
            "insights": ["根据现有数据推测，退款率处于正常波动范围"],
            "to_verify": ["退款原因分布需要进一步查询"],
            "confidence": 0.6,
        }
    emergency_script = [json.dumps(emergency_report, ensure_ascii=False)]
    return {
        "supervisor": _ScriptedChatModel(responses=[AIMessage(content=s) for s in supervisor_script]),
        "rag_researcher": _ScriptedChatModel(responses=[AIMessage(content=worker_script)]),
        "sql_analyst": _ScriptedChatModel(responses=[AIMessage(content=worker_script)]),
        "stock_analyst": _ScriptedChatModel(responses=[AIMessage(content=worker_script)]),
        "web_searcher": _ScriptedChatModel(responses=[AIMessage(content=worker_script)]),
        "reviewer": _ScriptedChatModel(responses=[AIMessage(content=s) for s in reviewer_script]),
        "emergency_synthesizer": _ScriptedChatModel(responses=[AIMessage(content=s) for s in emergency_script]),
    }


def ensure_kb(cfg) -> None:
    if not (PERSIST_DIR / "chroma.sqlite3").exists():
        print("知识库不存在，正在构建（data/kb -> storage/chroma）...")
        embeddings = build_embeddings(cfg)
        build_kb(DATA_DIR, PERSIST_DIR, embeddings)
        print("知识库构建完成。")


def build_runtime(
    cfg,
    question: str | None = None,
    include_reviewer: bool = True,
    include_guardrail: bool = True,
):
    ensure_kb(cfg)
    embeddings = build_embeddings(cfg)
    vectorstore = get_vectorstore(PERSIST_DIR, embeddings)
    tools = make_tools(vectorstore, db_path=DB_PATH)
    if cfg.provider == "mock":
        models = build_mock_models(question or "")
    else:
        # 分角色模型（P1-3）：主管用强模型，Worker 用轻量模型省成本
        models = {
            "supervisor": build_llm(cfg, cfg.supervisor_model),
            "reviewer": build_llm(cfg),
            "worker": build_llm(cfg, cfg.worker_model),
        }
    graph = build_graph(
        models,
        tools,
        max_iterations=cfg.max_iterations,
        include_reviewer=include_reviewer,
        include_guardrail=include_guardrail,
    )
    return graph


def build_orders_db(force: bool = False) -> None:
    """生成示例只读订单数据库（供 sql_analyst 使用）。"""
    if DB_PATH.exists() and not force:
        print(f"订单数据库已存在：{DB_PATH}（加 --force 重建）")
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS orders")
    conn.execute("DROP TABLE IF EXISTS inventory")
    conn.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            order_no TEXT,
            region TEXT,
            amount REAL,
            status TEXT,
            created_at TEXT
        )
        """
    )
    regions = ["华东", "华北", "华南", "西南"]
    rows = []
    idx = 1
    for year in (2025, 2026):
        for month in range(1, 13):
            if year == 2026 and month > 3:
                continue
            for _ in range(3):
                amount = round((idx * 137 + 500) % 3000 + 500, 2)
                if idx % 8 == 0:
                    status = "已退款"
                elif idx % 5 == 0:
                    status = "售后中"
                elif idx % 2 == 0:
                    status = "已完成"
                else:
                    status = "已支付"
                rows.append(
                    (
                        idx,
                        f"ORD-{year}{month:02d}-{idx:03d}",
                        regions[idx % 4],
                        amount,
                        status,
                        f"{year}-{month:02d}-{idx % 28 + 1:02d}",
                    )
                )
                idx += 1
    conn.executemany(
        "INSERT INTO orders (id, order_no, region, amount, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.execute(
        """
        CREATE TABLE inventory (
            id INTEGER PRIMARY KEY,
            sku TEXT,
            product_name TEXT,
            category TEXT,
            stock INTEGER,
            safety_stock INTEGER,
            status TEXT
        )
        """
    )
    inventory_rows = [
        (1, "SKU-1001", "锡兰红茶", "茶底", 320, 100, "正常"),
        (2, "SKU-1002", "鲜奶", "乳品", 12, 80, "低于安全库存"),
        (3, "SKU-1003", "珍珠", "小料", 0, 60, "缺货"),
        (4, "SKU-2001", "椰果", "小料", 240, 90, "正常"),
        (5, "SKU-2002", "芋圆", "小料", 45, 70, "低于安全库存"),
        (6, "SKU-3001", "纸杯", "包材", 500, 150, "正常"),
        (7, "SKU-3002", "封口膜", "包材", 88, 120, "低于安全库存"),
        (8, "SKU-4001", "柠檬", "鲜果", 660, 200, "正常"),
        (9, "SKU-4002", "芒果", "鲜果", 30, 100, "低于安全库存"),
        (10, "SKU-5001", "厚乳", "乳品", 410, 130, "正常"),
    ]
    conn.executemany(
        "INSERT INTO inventory (id, sku, product_name, category, stock, safety_stock, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        inventory_rows,
    )
    conn.commit()
    conn.close()
    print(f"订单数据库已生成：{DB_PATH}（{idx - 1} 条订单 + {len(inventory_rows)} 条库存）")


def print_trace(result: dict) -> None:
    print("\n===== 执行轨迹 =====")
    for entry in result.get("trace", []):
        node = entry.get("node")
        if node == "supervisor":
            print(f"[Supervisor] 第 {entry.get('iteration', 0)} 轮 -> 派给 {entry.get('next')}")
            if entry.get("instructions"):
                print(f"             指示: {entry['instructions']}")
        elif node == "reviewer":
            print(f"[Reviewer] verdict={entry.get('verdict')}")
            if entry.get("feedback"):
                print(f"           意见: {entry['feedback']}")
    print("\n[Researcher 发现]")
    for f in result.get("findings", []):
        print(f"  - {f.get('summary', '')}  ({f.get('source')} / {f.get('chunk_id')})")
    if result.get("analysis"):
        print("[Analyst 分析]")
        for a in result["analysis"]:
            print(f"  - {a.get('summary', '')}  ({a.get('chunk_id')})")
    if result.get("worker_report"):
        wr = result["worker_report"]
        print(
            f"[Worker 自检] self_check={wr.get('self_check')}  error={wr.get('error') or '-'}  "
            f"next_suggestion={wr.get('next_suggestion') or '-'}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-Agent RAG Supervisor")
    parser.add_argument("command", choices=["build-kb", "build-db", "ask", "mock", "serve"])
    parser.add_argument("question", nargs="?", default=None)
    parser.add_argument("--provider", choices=["openai", "ollama", "mock"], default=None)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--port", type=int, default=8000, help="serve 子命令的监听端口")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.provider)
    if args.max_iterations is not None:
        cfg.max_iterations = args.max_iterations

    if args.command == "serve":
        import uvicorn

        from app.api import app as api_app

        print(f"启动 API 服务：http://127.0.0.1:{args.port}（前端 dev 走 Vite :5173 代理）")
        uvicorn.run(api_app, host="127.0.0.1", port=args.port)
        return

    if args.command == "build-kb":
        embeddings = build_embeddings(cfg)
        build_kb(DATA_DIR, PERSIST_DIR, embeddings)
        print(f"知识库构建完成：{DATA_DIR} -> {PERSIST_DIR}")
        return

    if args.command == "build-db":
        build_orders_db(force=args.force)
        return

    if args.command == "mock":
        cfg.provider = "mock"
        question = args.question or "已支付但未开始制作的订单多久内可以申请退款？"
        print(f"Mock 演示问题：{question}\n")
    else:
        question = args.question

    if not question:
        question = input("请输入问题：").strip()

    graph = build_runtime(cfg, question)
    result = graph.invoke(initial_state(question))
    print_trace(result)
    print("\n===== 最终报告 =====")
    print(result.get("final_answer") or "(无输出)")
    print(f"\n共 {result.get('iterations', 0)} 轮 Supervisor 决策")
    print(f"[质量] quality={result.get('quality') or '未标注'}  finish_reason={result.get('finish_reason') or '未标注'}")
    if result.get("emergency_report"):
        conf = result["emergency_report"].get("confidence")
        print(f"[紧急综合] 阶段快报置信度={conf}")
    if result.get("guardrail"):
        g = result["guardrail"]
        print(f"[规则门控] passed={g['passed']}  reason={g['reason']}")


if __name__ == "__main__":
    main()
