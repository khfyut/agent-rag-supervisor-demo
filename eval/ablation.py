"""消融实验（对照第 7 章 7.4）：同一评估集跑多个 Harness 变体，对比分数。

变体：
- full：完整版（Supervisor + 角色池 + Reviewer + Guardrail）；
- no_reviewer：去掉 Reviewer 质检（评审节点直接放行）；
- no_guardrail：去掉降级规则门控（emergency 直接结束）。

判断（原书方法）：
- 分数大跌 → 该组件是关键；
- 几乎没差 → 组件可删（省 token / 延迟）。

模型替换实验：固定 Harness 换模型（改 LLM_PROVIDER / SUPERVISOR_MODEL / WORKER_MODEL
后重跑），对比分数波动即可区分「模型瓶颈」和「Harness 瓶颈」。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from main import build_runtime  # noqa: E402
from app.core.config import load_config  # noqa: E402
from app.orchestration.graph import initial_state  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent / "cases.json"

VARIANTS = [
    ("full", True, True),
    ("no_reviewer", False, True),
    ("no_guardrail", True, False),
]


def run_variant(cfg, cases, include_reviewer: bool, include_guardrail: bool) -> dict:
    rows = []
    for case in cases:
        graph = build_runtime(
            cfg,
            question=case["question"],
            include_reviewer=include_reviewer,
            include_guardrail=include_guardrail,
        )
        result = graph.invoke(initial_state(case["question"]))
        answer = result.get("final_answer") or ""
        keywords_hit = [k for k in case["required_keywords"] if k in answer]
        rows.append(
            {
                "id": case["id"],
                "success": len(keywords_hit) == len(case["required_keywords"]),
                "quality": result.get("quality", ""),
            }
        )
    total = len(rows)
    return {
        "cases": total,
        "success_rate": round(sum(r["success"] for r in rows) / total, 4) if total else 0,
        "verified_rate": round(
            sum(1 for r in rows if r["quality"] == "verified") / total, 4
        )
        if total
        else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="消融实验：对比 Harness 组件贡献")
    parser.add_argument("--provider", choices=["openai", "ollama", "deepseek", "minimax", "mock"], default=None)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    cfg = load_config(args.provider)
    if args.max_iterations is not None:
        cfg.max_iterations = args.max_iterations
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if args.limit:
        cases = cases[: args.limit]

    print(f"评估集：{len(cases)} 个用例（provider={cfg.provider}）\n")
    results = {}
    for name, reviewer, guardrail in VARIANTS:
        print(f"运行变体：{name} ...", flush=True)
        results[name] = run_variant(cfg, cases, reviewer, guardrail)
        r = results[name]
        print(f"  {name}: 成功率 {r['success_rate']:.1%}，verified 率 {r['verified_rate']:.1%}")

    print("\n=== 对比结论 ===")
    full = results["full"]["success_rate"]
    if full:
        for name in ("no_reviewer", "no_guardrail"):
            delta = full - results[name]["success_rate"]
            verdict = "关键组件（去掉后明显下降）" if delta > 0.1 else "贡献有限（可考虑精简）"
            print(f"  去掉 {name}：成功率 {full:.1%} -> {results[name]['success_rate']:.1%}（Δ{delta:+.1%}）→ {verdict}")


if __name__ == "__main__":
    main()
