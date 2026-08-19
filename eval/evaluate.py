"""评估台（对照第 7 章）：任务集 + 运行器 + LLM-as-a-Judge + 质量/过程指标。

指标：
- 质量：任务成功率（关键词）、LLM-as-a-Judge 平均分（可选 --judge）；
- 过程：工具调用正确率（期望工具 vs 实际派发）、平均迭代轮数、平均 token、平均工具调用次数；
- 降级：降级触发率 / 降级交付率 / 诚实失败率 / 门控拦截次数。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from main import build_runtime  # noqa: E402
from app.core.config import load_config  # noqa: E402
from app.orchestration.graph import initial_state  # noqa: E402
from eval.judge import judge  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent / "cases.json"
REPORT_DIR = Path(__file__).resolve().parent / "reports"
CASE_TIMEOUT = 240  # 单用例最长执行时间（秒）；超时记为 timeout，避免单题卡死拖垮整轮评估


def _norm(text: str) -> str:
    """归一化空白，避免「24 小时」与「24小时」误判。"""
    return re.sub(r"\s+", "", text or "")


def _tool_accuracy(result: dict, expected: list[str]) -> bool:
    """期望工具 vs 实际派发：boundary 期望空（不该派专家）；
    normal/composite/trap 期望的专家必须全部实际派发（复合题要求多专家接力）。"""
    dispatched = {
        t["next"]
        for t in result.get("trace", [])
        if t.get("node") == "supervisor" and t.get("next") not in ("finish", "emergency")
    }
    if not expected:
        return len(dispatched) == 0
    return set(expected) <= dispatched


def _process_metrics(result: dict) -> dict:
    """从消息历史统计过程指标：工具调用次数、token 总量。"""
    messages = result.get("messages", [])
    tool_calls = sum(1 for m in messages if getattr(m, "tool_calls", None))
    tokens = sum(
        (getattr(m, "usage_metadata", None) or {}).get("total_tokens", 0)
        for m in messages
    )
    return {"tool_calls": tool_calls, "tokens": tokens}


def _invoke_with_timeout(graph, case: dict) -> dict | None:
    """带看门狗的图执行：超过 CASE_TIMEOUT 返回 None（底层线程为 daemon，不阻塞进程退出）。"""
    import threading

    box: dict[str, Any] = {}

    def run() -> None:
        box["result"] = graph.invoke(initial_state(case["question"]))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout=CASE_TIMEOUT)
    if thread.is_alive():
        return None
    return box.get("result") or {}


def _write_report(cfg, results, use_judge, out_path: Path) -> None:
    total = len(results)
    success_count = sum(1 for r in results if r["success"])
    tool_ok = sum(1 for r in results if r["tool_accurate"])
    passed_reviews = sum(1 for r in results if r["reviewer_verdicts"] and r["reviewer_verdicts"][-1] == "pass")
    review_rounds = sum(1 for r in results if r["reviewer_verdicts"])
    degraded = [r for r in results if r["quality"] in ("partial", "failed")]
    partial = [r for r in degraded if r["quality"] == "partial"]
    failed = [r for r in degraded if r["quality"] == "failed"]
    blocked_hallucinations = sum(
        1 for r in results if "编造" in r["guardrail_reason"] or "不存在" in r["guardrail_reason"]
    )
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "provider": cfg.provider,
        "model": cfg.llm_model,
        "total_cases": total,
        "task_success_rate": round(success_count / total, 4) if total else 0,
        "tool_accuracy_rate": round(tool_ok / total, 4) if total else 0,
        "reviewer_pass_rate": round(passed_reviews / review_rounds, 4) if review_rounds else 0,
        "avg_iterations": round(sum(r["iterations"] for r in results) / total, 2) if total else 0,
        "avg_tool_calls": round(sum(r["tool_calls"] for r in results) / total, 2) if total else 0,
        "avg_tokens": round(sum(r["tokens"] for r in results) / total, 2) if total else 0,
        "avg_elapsed_s": round(sum(r["elapsed_s"] for r in results) / total, 2) if total else 0,
        "degradation_rate": round(len(degraded) / total, 4) if total else 0,
        "degradation_delivery_rate": round(len(partial) / len(degraded), 4) if degraded else 0,
        "honest_failure_rate": round(len(failed) / total, 4) if total else 0,
        "hallucination_blocked": blocked_hallucinations,
        "cases": results,
    }
    if use_judge:
        report["avg_judge_score"] = round(
            sum(r.get("judge_score", 0) for r in results) / total, 2
        ) if total else 0
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def evaluate(
    cfg,
    limit: int | None = None,
    use_judge: bool = False,
    offset: int = 0,
    out_path: Path | None = None,
) -> dict:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if offset:
        cases = cases[offset:]
    if limit:
        cases = cases[:limit]
    results = []

    for case in cases:
        graph = build_runtime(cfg, question=case["question"])
        start = time.time()
        result = _invoke_with_timeout(graph, case)
        if result is None:
            elapsed = round(time.time() - start, 2)
            entry = {
                "id": case["id"],
                "type": case.get("type", "normal"),
                "level": case["level"],
                "success": False,
                "keywords_hit": [],
                "missing_keywords": list(case.get("required_keywords", [])),
                "tool_accurate": False,
                "iterations": 0,
                "tool_calls": 0,
                "tokens": 0,
                "elapsed_s": elapsed,
                "citations": [],
                "citation_valid": False,
                "reviewer_verdicts": [],
                "final_answer": "",
                "quality": "timeout",
                "finish_reason": "case_timeout",
                "guardrail_reason": "",
                "trace": [],
            }
            results.append(entry)
            if out_path:
                _write_report(cfg, results, use_judge, out_path)
            print(
                f"  [{case['id']}] ({case.get('type')}) 超时（>{CASE_TIMEOUT}s）quality=timeout",
                flush=True,
            )
            continue
        elapsed = round(time.time() - start, 2)

        answer = result.get("final_answer") or ""
        norm_answer = _norm(answer)
        keywords_hit = [k for k in case["required_keywords"] if _norm(k) in norm_answer]
        success = len(keywords_hit) == len(case["required_keywords"])
        proc = _process_metrics(result)
        reviewer_entries = [t for t in result.get("trace", []) if t.get("node") == "reviewer"]
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
            "missing_keywords": [k for k in case["required_keywords"] if _norm(k) not in norm_answer],
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
        if use_judge:
            verdict = judge(cfg, case, answer)
            entry["judge_score"] = verdict["score"]
            entry["judge_reason"] = verdict["reason"]

        results.append(entry)
        if out_path:
            _write_report(cfg, results, use_judge, out_path)
        judge_note = f" judge={entry.get('judge_score', '-')}" if use_judge else ""
        print(
            f"  [{case['id']}] ({case.get('type')}) 完成 {elapsed}s "
            f"quality={result.get('quality', '') or '-'}{judge_note}",
            flush=True,
        )

    return _write_report(cfg, results, use_judge, out_path or (REPORT_DIR / "_tmp.json"))


def main() -> None:
    # Windows 中文控制台（GBK）无法编码 ✓/✗ 等符号，统一按 UTF-8 输出并容错，避免打印崩溃
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - 非标准输出场景下跳过即可
        pass
    parser = argparse.ArgumentParser(description="运行评估集（第 7 章评估台）")
    parser.add_argument("--provider", choices=["openai", "ollama", "deepseek", "minimax", "mock"], default=None)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 个用例")
    parser.add_argument("--offset", type=int, default=0, help="跳过前 N 个用例（断点续跑）")
    parser.add_argument("--judge", action="store_true", help="启用 LLM-as-a-Judge 打分")
    args = parser.parse_args()

    cfg = load_config(args.provider)
    if args.max_iterations is not None:
        cfg.max_iterations = args.max_iterations

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = REPORT_DIR / f"report_{tag}.json"
    report = evaluate(cfg, limit=args.limit, use_judge=args.judge, offset=args.offset, out_path=out_path)

    print(f"任务成功率: {report['task_success_rate']:.1%}")
    print(f"工具调用正确率: {report['tool_accuracy_rate']:.1%}")
    print(f"审查打回率: {report['reviewer_pass_rate']:.1%}")
    print(f"平均迭代轮数: {report['avg_iterations']}  平均工具调用: {report['avg_tool_calls']}  平均 token: {report['avg_tokens']}")
    print(f"平均耗时: {report['avg_elapsed_s']}s")
    print(f"降级触发率: {report['degradation_rate']:.1%}")
    print(f"降级交付率(partial): {report['degradation_delivery_rate']:.1%}")
    print(f"诚实失败率(failed): {report['honest_failure_rate']:.1%}")
    print(f"门控拦截编造引用: {report['hallucination_blocked']} 次")
    if "avg_judge_score" in report:
        print(f"LLM-as-a-Judge 平均分: {report['avg_judge_score']}/5")

    print("\n分类汇总：")
    for typ in ("normal", "boundary", "trap", "composite"):
        subset = [r for r in report["cases"] if r["type"] == typ]
        if subset:
            rate = sum(r["success"] for r in subset) / len(subset)
            tool_rate = sum(r["tool_accurate"] for r in subset) / len(subset)
            print(f"  {typ}: {len(subset)} 用例，成功率 {rate:.0%}，工具正确率 {tool_rate:.0%}")

    print("\n逐条结果：")
    for r in report["cases"]:
        mark = "PASS" if r["success"] else "FAIL"
        tool = "T✓" if r["tool_accurate"] else "T✗"
        print(
            f"  [{mark}/{tool}] {r['id']} ({r['type']}/{r['level']}) "
            f"缺关键词: {r['missing_keywords'] or '-'} quality={r['quality'] or '-'}"
        )
    print(f"\n报告已保存: {out_path}")


if __name__ == "__main__":
    main()
