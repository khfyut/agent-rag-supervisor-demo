"""规则门控（Guardrail）：无 LLM 参与的确定性校验。

轮次耗尽后，emergency_synthesizer 产出的阶段快报必须经过这里：
1. 结构完整性：summary 非空，三区块齐全；
2. 引用真实性：Fact.chunk_id 若非空，必须能在 findings/analysis 中找到；
3. 诚实度：confidence 必须存在且落在 0~1。

通过 → quality=partial（带免责声明的阶段快报）；
不通过 → quality=failed（诚实告知原因，附已有信息）。
"""

from __future__ import annotations

from typing import Any, Callable

from .state import AgentState


def validate_emergency_report(
    report: dict[str, Any],
    findings: list[dict[str, Any]],
    analysis: list[dict[str, Any]],
) -> tuple[bool, str]:
    """返回 (是否通过, 失败原因)。"""
    # 1. 结构完整性
    if not (report.get("summary") or "").strip():
        return False, "summary 为空"
    facts = report.get("confirmed_facts") or []
    insights = report.get("insights") or []
    to_verify = report.get("to_verify") or []
    if not facts:
        return False, "confirmed_facts 为空"
    if not insights:
        return False, "insights 为空"
    if not to_verify:
        return False, "to_verify 为空"

    # 2. 引用真实性：声明了 chunk_id 就必须能在产出中找到
    known = {
        item.get("chunk_id")
        for item in list(findings) + list(analysis)
        if item.get("chunk_id")
    }
    for fact in facts:
        cid = (fact.get("chunk_id") or "").strip()
        if cid and cid not in known:
            return False, f"引用 {cid} 在 findings/analysis 中不存在（疑似编造）"

    # 3. 诚实度：置信度必须存在且合理
    confidence = report.get("confidence")
    if confidence is None or not isinstance(confidence, (int, float)):
        return False, "confidence 缺失或类型错误"
    if not (0 <= float(confidence) <= 1):
        return False, "confidence 超出 0~1 范围"

    return True, ""


def build_partial_report(report: dict[str, Any]) -> str:
    """通过门控时组装 Markdown 阶段快报。"""
    lines = [
        "> ⚠️ 以下为阶段性快报（未完成全量质检），结论置信度："
        f"{report.get('confidence')}",
        "",
        f"**一句话结论**：{report.get('summary')}",
        "",
        "**已确认事实**",
    ]
    for fact in report.get("confirmed_facts") or []:
        cid = fact.get("chunk_id") or ""
        suffix = f"（引用：{cid}）" if cid else ""
        lines.append(f"- {fact.get('statement')}{suffix}")
    lines += ["", "**初步洞察（基于现有数据的推测）**"]
    lines += [f"- {item}" for item in report.get("insights") or []]
    lines += ["", "**需后续核实**"]
    lines += [f"- {item}" for item in report.get("to_verify") or []]
    return "\n".join(lines)


def build_failed_report(report: dict[str, Any], reason: str, findings: list[dict[str, Any]]) -> str:
    """未通过门控时输出诚实降级消息。"""
    lines = [
        "无法完成完整回答，以下是原因和已收集到的信息，供你自行判断：",
        "",
        f"**降级原因**：{reason}",
        "",
        "**已有发现（前 3 条）**",
    ]
    for item in (findings or [])[:3]:
        lines.append(f"- {item.get('summary', '')}")
    return "\n".join(lines)


def make_guardrail_node() -> Callable[[AgentState], dict[str, Any]]:
    """纯规则节点：不调用任何 LLM。"""

    def node(state: AgentState) -> dict[str, Any]:
        report = state.get("emergency_report") or {}
        findings = state.get("findings", [])
        analysis = state.get("analysis", [])
        passed, reason = validate_emergency_report(report, findings, analysis)
        if passed:
            quality = "partial"
            final_answer = build_partial_report(report)
        else:
            quality = "failed"
            final_answer = build_failed_report(report, reason, findings)
        guardrail = {"passed": passed, "quality": quality, "reason": reason}
        trace_entry = {"node": "guardrail", **guardrail}
        return {
            "guardrail": guardrail,
            "quality": quality,
            "finish_reason": "guardrail_" + quality,
            "final_answer": final_answer,
            "trace": [trace_entry],
            "debug": {
                "input": {
                    "report": report,
                    "findings": findings,
                    "analysis": analysis,
                },
                "output": guardrail,
            },
        }

    return node
