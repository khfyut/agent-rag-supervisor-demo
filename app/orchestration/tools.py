"""Agent 工具工厂：检索、引用核验、只读 SQL 查询、网络搜索。"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.tools import tool

from app.knowledge import rag


def make_tools(vectorstore: Chroma, db_path: Path | None = None) -> dict[str, Any]:
    @tool
    def search_knowledge(query: str, k: int = 4) -> list[dict[str, Any]]:
        """在内部知识库中检索与 query 相关的内容，返回带引用来源（source/chunk_id）的片段。"""
        return rag.search_knowledge(vectorstore, query, k=k)

    @tool
    def verify_citations(chunk_ids: list[str]) -> dict[str, Any]:
        """核验给定的引用 chunk_id 是否真实存在于知识库，返回有效与缺失列表。"""
        return rag.verify_citations(vectorstore, chunk_ids)

    def _schema_hint() -> str:
        """动态读取数据库表结构，写进工具描述——让模型知道有哪些列可用。"""
        if db_path is None or not db_path.exists():
            return "（数据库未初始化）"
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            lines = []
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            for (table,) in tables:
                columns = [
                    f"{row[1]}({row[2]})"
                    for row in conn.execute(f"PRAGMA table_info({table})")
                ]
                sample = conn.execute(f"SELECT * FROM {table} LIMIT 1").fetchone()
                lines.append(
                    f"表 {table}: 列={columns}；示例行={sample}"
                )
            return "\n".join(lines)
        except Exception:  # noqa: BLE001
            return "（无法读取 schema）"
        finally:
            conn.close()

    schema_hint = _schema_hint()

    def query_sql_impl(sql: str) -> Any:
        """只读 SELECT 查询（docstring 在下方动态注入 schema）。"""
        if not sql.strip().upper().startswith("SELECT"):
            return {"error": "只允许 SELECT 查询"}
        if db_path is None or not db_path.exists():
            return {"error": "订单数据库不存在，请先运行 python main.py build-db"}
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            cur = conn.execute(sql)
            columns = [d[0] for d in cur.description]
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows[:100]]
        except Exception as exc:  # noqa: BLE001 - 把错误信息返回给 Agent 用于自我纠错
            return {"error": str(exc)}
        finally:
            conn.close()

    query_sql_impl.__doc__ = (
        "在只读订单数据库中执行 SELECT 查询并返回结果（最多 100 行）。\n\n"
        "数据库结构（列名必须以这里为准）：\n"
        f"{schema_hint}"
    )
    query_sql = tool(query_sql_impl)

    @tool
    def run_python(code: str) -> dict[str, Any]:
        """在隔离的 Python 沙盒中执行数据分析代码（进程级隔离 + 临时目录 + 超时限制）。

        用于对 query_sql 的结果做聚合、统计、趋势计算或可视化等精确计算。
        安全边界：独立解释器（-I -B）+ 临时工作目录 + 15 秒超时 + 输出截断；
        脚本可通过环境变量 DATASET_READONLY 只读访问订单数据库路径。
        禁止尝试访问网络或读取工作目录之外的文件。
        """
        with tempfile.TemporaryDirectory(prefix="agent_sandbox_") as tmp:
            script_path = Path(tmp) / "script.py"
            script_path.write_text(textwrap.dedent(code), encoding="utf-8")
            env = {
                "PYTHONIOENCODING": "utf-8",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            if db_path is not None:
                env["DATASET_READONLY"] = str(db_path)
            try:
                proc = subprocess.run(
                    [sys.executable, "-I", "-B", str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    cwd=tmp,
                    env=env,
                    encoding="utf-8",
                    errors="replace",
                )
                return {
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout[-3000:],
                    "stderr": proc.stderr[-2000:],
                }
            except subprocess.TimeoutExpired:
                return {"error": "执行超过 15 秒被终止，请简化代码或分步执行"}
            except Exception as exc:  # noqa: BLE001
                return {"error": f"沙盒执行失败: {exc}"}

    @tool
    def search_web(query: str, max_results: int = 5) -> Any:
        """搜索外部公开网页，返回标题/摘要/链接；适合需要联网获取最新信息的问题。

        优先使用 TAVILY_API_KEY（推荐）；未配置时回退 DuckDuckGo；
        两者都不可用时返回错误信息，Agent 应如实报告而不是编造。
        """
        tavily_key = os.getenv("TAVILY_API_KEY")
        if tavily_key:
            try:
                from langchain_community.tools import TavilySearchResults

                results = TavilySearchResults(
                    api_key=tavily_key, max_results=max_results
                ).invoke(query)
                return [
                    {
                        "title": r.get("title", ""),
                        "body": r.get("content", r.get("snippet", "")),
                        "href": r.get("url", ""),
                    }
                    for r in results
                ]
            except Exception as exc:  # noqa: BLE001
                return {"error": f"Tavily 搜索失败: {exc}"}
        try:
            from duckduckgo_search import DDGS

            with DDGS(timeout=10) as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            return [
                {
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "href": r.get("href", ""),
                }
                for r in results
            ]
        except Exception as exc:  # noqa: BLE001
            return {
                "error": (
                    f"网络搜索不可用（{exc}）。请配置 TAVILY_API_KEY 或检查网络连接，"
                    "或让主管改用内部知识库/订单库回答。"
                )
            }

    return {
        "search_knowledge": search_knowledge,
        "verify_citations": verify_citations,
        "query_sql": query_sql,
        "run_python": run_python,
        "search_web": search_web,
    }
