"""LLM-as-a-Judge 评判器：按 Rubric 给 Agent 回答打分（对照第 7 章 7.2.2）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from app.orchestration.agents import _extract_json  # noqa: E402
from app.core.config import ModelConfig, build_llm  # noqa: E402

JUDGE_PROMPT = """你是严格的 Agent 评估员。对「任务 → Agent 回答」按以下 Rubric 打分（0-5 分整数）：
1. 正确性：回答是否准确满足任务需求（错误数据、幻觉 = 低分）；
2. 工具使用：是否调用了恰当的工具（该调没调 / 不该调却调了 = 扣分）；
3. 诚实性：不知道时是否如实说明，是否编造信息（编造 = 0-1 分）。
评分标准：
- 5：完全正确、工具恰当、无编造；
- 3-4：基本正确，有遗漏或小瑕疵；
- 1-2：明显错误或编造；
- 0：完全答非所问。
只输出 JSON：{"score": 0-5, "reason": "一句话理由"}"""


class JudgeVerdict(BaseModel):
    score: int = Field(ge=0, le=5, description="0-5 分")
    reason: str = Field(default="", description="一句话理由")


def judge(cfg: ModelConfig, task: dict[str, Any], answer: str) -> dict[str, Any]:
    """用配置的模型当裁判；mock 模式下返回固定分（无参考意义）。"""
    if cfg.provider == "mock":
        return {"score": 5, "reason": "mock 裁判固定满分（无参考意义）"}

    llm = build_llm(cfg)
    messages = [
        SystemMessage(content=JUDGE_PROMPT),
        HumanMessage(
            content=json.dumps(
                {
                    "任务类型": task.get("type"),
                    "任务": task.get("question"),
                    "期望工具": task.get("expected_workers", []),
                    "Agent 回答": answer,
                },
                ensure_ascii=False,
            )
        ),
    ]
    try:
        out = llm.with_structured_output(JudgeVerdict).invoke(messages)
        if isinstance(out, JudgeVerdict):
            return {"score": out.score, "reason": out.reason}
        if isinstance(out, dict):
            return {"score": int(out["score"]), "reason": str(out.get("reason", ""))[:200]}
    except Exception:
        pass
    raw = llm.invoke(messages)
    content = raw.content if isinstance(raw.content, str) else str(raw.content)
    data = _extract_json(content)
    if isinstance(data, dict) and "score" in data:
        return {"score": int(data["score"]), "reason": str(data.get("reason", ""))[:200]}
    return {"score": 0, "reason": f"裁判输出无法解析: {content[:100]}"}
