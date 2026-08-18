"""Agent 节点：Supervisor / Reviewer 结构化决策节点 + 角色池 Worker 工厂。"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Literal, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from .registry import WORKER_REGISTRY, worker_descriptions, worker_names
from .state import AgentState


class SupervisorDecision(BaseModel):
    """Supervisor 每轮的输出：决定下一步派给谁。"""

    next: str = Field(
        description="从角色池中选择的专家名，或 reviewer / finish；只有任务完成时才选择 finish"
    )
    instructions: str = Field(default="", description="给下一个角色的工作指示")
    draft: Optional[str] = Field(
        default=None, description="派 reviewer 前，基于已有发现生成的报告草稿"
    )
    final_answer: Optional[str] = Field(
        default=None, description="仅当 next=finish 时，输出最终答案"
    )


class ReviewVerdict(BaseModel):
    """Reviewer 的质检结论。"""

    verdict: Literal["pass", "fail"] = Field(description="报告是否通过质检")
    feedback: str = Field(default="", description="不通过时给出的修改意见")
    revised_report: Optional[str] = Field(
        default=None, description="修改后的最终报告（通过时输出定稿）"
    )


class Fact(BaseModel):
    """已确认事实：必须可溯源。"""

    statement: str = Field(description="事实陈述")
    chunk_id: str = Field(default="", description="来源片段 ID；无法溯源则留空")


class EmergencyReport(BaseModel):
    """轮次耗尽时的阶段快报：带置信度标注，禁止硬编。"""

    summary: str = Field(description="一句话结论")
    confirmed_facts: list[Fact] = Field(description="已确认事实，每条尽量带 chunk_id 引用")
    insights: list[str] = Field(description="初步洞察，必须是基于现有数据的推测")
    to_verify: list[str] = Field(description="需后续核实的事项")
    confidence: float = Field(ge=0, le=1, description="对结论的置信度 0~1")


SUPERVISOR_PROMPT = """你是一个多 Agent 团队的主管（Supervisor）。你的团队有以下可调度的专家（角色池）：
{worker_descriptions}

另外还有 reviewer：质检员，审查最终报告（覆盖度、引用真实性、幻觉），不合格会打回。

决策规则：
1. 根据用户问题类型，从角色池中选择最合适的专家；问题需要多类信息（如数据 + 规则、库存 + 规则）时，可跨多轮依次调度多个专家，已积累的 findings 会保留并供后续专家参考；
2. 如果已有发现但还没有报告草稿，先基于 findings 生成 draft，然后派 reviewer；
3. 如果 review 的 verdict=pass，或已超过最大轮次，选择 finish 并输出 final_answer；
4. 如果角色池中没有任何专家能处理，选择 finish 并诚实说明无法处理。

不要编造知识库或数据库中不存在的内容。"""

SUPERVISOR_OUTPUT_FORMAT = """
输出格式（严格 JSON，字段名必须为 next / instructions / draft / final_answer）：
{"next": "专家名或reviewer或finish", "instructions": "给下一个角色的工作指示", "draft": "报告草稿（可选）", "final_answer": "最终答案（仅 finish 时输出）"}
示例：{"next": "sql_analyst", "instructions": "查询华东区 2026 年第一季度的订单量", "draft": "", "final_answer": ""}
"""


REVIEWER_PROMPT = """你是质检员。审查草稿报告是否满足：
1. 覆盖用户问题的所有关键点；
2. 引用的 chunk_id 都来自 findings/analysis，且真实存在；
3. 没有编造知识库之外的信息，格式清晰。
输出结论：verdict 为 pass 或 fail；fail 时给出具体 feedback；pass 时输出修订后的定稿 revised_report。
输出格式（严格 JSON，字段名必须一致）：
{"verdict": "pass", "feedback": "修改意见（可选）", "revised_report": "定稿报告（pass 时必填）"}"""


EMERGENCY_SYNTHESIS_PROMPT = """你是紧急综合员。系统在轮次耗尽时调用你，把已有发现整理成阶段快报。
规则：
1. 严禁发散，只基于 findings/analysis 中的内容；
2. 三区块必须齐全：confirmed_facts（已确认事实）、insights（初步洞察，标注为推测）、to_verify（需后续核实项）；
3. 每个已确认事实尽量带 chunk_id 引用；没有把握的引用留空，禁止编造不存在的引用；
4. confidence 表示你对结论的整体置信度（0~1），禁止虚高；
5. 输出严格 JSON，符合以下结构（字段名必须一致）：
{"summary": "一句话结论", "confirmed_facts": [{"statement": "已确认事实", "chunk_id": "来源ID或空串"}], "insights": ["推测1"], "to_verify": ["待核实1"], "confidence": 0.6}"""


def _extract_json(text: str) -> Any | None:
    """从模型输出中提取 JSON（支持 ```json 代码块）。"""
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        return None


def _extract_json_array(text: str) -> list[dict[str, Any]] | None:
    data = _extract_json(text)
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    return None


def _serialize_messages(messages: list, limit: int = 4000) -> list[dict[str, Any]]:
    """把节点的 ReAct 消息链序列化成可读日志：AI 思考文本、工具调用、工具返回按顺序保留。"""
    log: list[dict[str, Any]] = []
    for msg in messages or []:
        content = getattr(msg, "content", "")
        if not isinstance(content, str):
            content = str(content)
        entry: dict[str, Any] = {"role": getattr(msg, "type", ""), "content": content[:limit]}
        tool_calls = getattr(msg, "tool_calls", None) or []
        if tool_calls:
            entry["tool_calls"] = [
                {"name": tc.get("name", ""), "args": tc.get("args", {})} for tc in tool_calls
            ]
        if getattr(msg, "tool_call_id", None):
            entry["tool_call_id"] = msg.tool_call_id
        if getattr(msg, "name", None):
            entry["name"] = msg.name
        log.append(entry)
    return log


def invoke_structured(
    model: BaseChatModel, schema: type[BaseModel], messages: list
) -> BaseModel:
    """优先走 with_structured_output，失败则回退手动 JSON 解析（兼容小模型）。"""
    def _normalize(data: dict) -> dict:
        """字段名容错：不同模型可能用 selected_worker/worker/agent 等别名代替 next。"""
        # 解包：模型可能用类名包一层，如 {"EmergencyReport": {...}}
        if len(data) == 1:
            only_value = next(iter(data.values()))
            if isinstance(only_value, dict) and not any(
                k in data for k in ("next", "summary", "verdict")
            ):
                data = only_value
        # summary 缺失时从常见别名补齐
        if "summary" not in data:
            for key in ("conclusion", "result", "answer", "summary_text"):
                if key in data:
                    data["summary"] = data[key]
                    break
        # confirmed_facts 字段映射：fact -> statement、chunk_id 空值补 ""、元素可能是字符串
        facts = data.get("confirmed_facts")
        if isinstance(facts, list):
            normalized_facts = []
            for f in facts:
                if isinstance(f, dict):
                    item = dict(f)
                    if "fact" in item and "statement" not in item:
                        item["statement"] = item["fact"]
                    item.setdefault("statement", str(item.get("summary", "")))
                    cid = item.get("chunk_id")
                    item["chunk_id"] = cid if isinstance(cid, str) else ""
                    normalized_facts.append(item)
                elif isinstance(f, str):
                    normalized_facts.append({"statement": f, "chunk_id": ""})
            data["confirmed_facts"] = normalized_facts
        # insights / to_verify 元素可能是 {"insight": ...} 等 dict
        for field in ("insights", "to_verify"):
            values = data.get(field)
            if isinstance(values, list):
                data[field] = [
                    (
                        item.get("insight")
                        or item.get("content")
                        or item.get("text")
                        or item.get("item")
                        or str(item)
                    )
                    if isinstance(item, dict)
                    else item
                    for item in values
                ]
        aliases = {
            "next": ("next", "next_agent", "selected_worker", "worker", "agent", "action"),
            "instructions": ("instructions", "instruction", "task", "message"),
            "draft": ("draft", "report_draft", "draft_report"),
            "final_answer": ("final_answer", "final", "answer", "response"),
        }
        for field, names in aliases.items():
            if field not in data:
                for name in names:
                    if name in data:
                        data[field] = data[name]
                        break
        return data

    if getattr(model, "is_scripted", False):
        raw = model.invoke(messages)
        content = raw.content if isinstance(raw.content, str) else str(raw.content)
        data = _extract_json(content)
        if isinstance(data, dict):
            return schema.model_validate(_normalize(data))
        raise ValueError(f"脚本输出无法解析: {content[:200]}")
    try:
        out = model.with_structured_output(schema).invoke(messages)
        if isinstance(out, schema):
            return out
        if isinstance(out, dict):
            return schema.model_validate(_normalize(out))
    except Exception:
        pass
    raw = model.invoke(messages)
    content = raw.content if isinstance(raw.content, str) else str(raw.content)
    data = _extract_json(content)
    if isinstance(data, dict):
        return schema.model_validate(_normalize(data))
    # 输出截断/格式异常时重试一次（模型可能给出更短更规范的 JSON）
    raw = model.invoke(messages)
    content = raw.content if isinstance(raw.content, str) else str(raw.content)
    data = _extract_json(content)
    if isinstance(data, dict):
        return schema.model_validate(_normalize(data))
    raise ValueError(f"无法从模型输出解析结构化结果: {content[:200]}")


def make_supervisor_node(
    model: BaseChatModel, max_iterations: int
) -> Callable[[AgentState], dict[str, Any]]:
    def compact(items: list[dict[str, Any]] | None, limit: int = 150) -> list[dict[str, Any]]:
        """上下文瘦身：主管只看结论摘要，不看过程全量（防止上下文膨胀 + 思维惯性）。"""
        return [
            {
                "summary": (item.get("summary") or "")[:limit],
                "source": item.get("source"),
                "chunk_id": item.get("chunk_id"),
            }
            for item in (items or [])[:5]
        ]

    def node(state: AgentState) -> dict[str, Any]:
        review = state.get("review") or {}
        feedback = state.get("feedback", [])
        iterations = state.get("iterations", 0)
        draft = state.get("draft", "")

        context = {
            "question": state["question"],
            "findings_summary": compact(state.get("findings", [])),
            "analysis_summary": compact(state.get("analysis", [])),
            "draft_preview": (draft or "")[:500],
            "review": review,
            "feedback": feedback,
            "last_worker_report": state.get("worker_report") or {},
        }
        messages = [
            SystemMessage(
                content=SUPERVISOR_PROMPT.format(worker_descriptions=worker_descriptions())
                + SUPERVISOR_OUTPUT_FORMAT
            ),
            HumanMessage(content=json.dumps(context, ensure_ascii=False)),
        ]
        decision = invoke_structured(model, SupervisorDecision, messages)

        out: dict[str, Any] = {
            "iterations": iterations + 1,
        }

        # 强制收尾拆成两条路：
        # 1) 质检通过 → 正常交付（verified）
        # 2) 轮次耗尽 → 走紧急综合 + 规则门控（不交半成品）
        if review.get("verdict") == "pass":
            decision = SupervisorDecision(
                next="finish",
                final_answer=review.get("revised_report") or draft or decision.final_answer,
            )
            out["quality"] = "verified"
            out["finish_reason"] = "review_pass"
        elif iterations >= max_iterations:
            decision = SupervisorDecision(
                next="emergency",
                instructions="轮次耗尽，进入紧急综合节点生成阶段快报",
            )
            out["finish_reason"] = "iterations_exhausted"

        # 白名单校验：模型只能从角色池中选专家（安全边界由代码硬控）
        # 降级路径（emergency）只能由代码触发，模型不允许主动选择
        allowed = set(worker_names()) | {"reviewer", "finish"}
        if decision.next not in allowed:
            decision = SupervisorDecision(
                next=WORKER_REGISTRY[0].name,
                instructions="未识别的专家名，回退到默认专家：" + decision.instructions,
                draft=decision.draft,
                final_answer=decision.final_answer,
            )

        if decision.next == "finish" and not decision.final_answer:
            decision.final_answer = draft

        # 收尾保护：发现为空或 Worker 自检异常时，不许直接 finish（先质检，不交半成品）
        worker_report = state.get("worker_report") or {}
        findings = state.get("findings", [])
        worker_failed = worker_report.get("self_check") not in (None, "", "ok")
        if (
            decision.next == "finish"
            and review.get("verdict") != "pass"
            and (not findings or worker_failed)
        ):
            decision = SupervisorDecision(
                next="reviewer",
                instructions="发现为空或 Worker 自检异常：先派 reviewer 质检评估，不要直接收尾",
            )

        # 必须在所有决策改写之后序列化，路由读取的是最新 decision
        out["decision"] = decision.model_dump()
        # 任务自包含：把主管指令传给 Worker（P0-1）
        out["task_instructions"] = decision.instructions
        out["trace"] = [
            {
                "node": "supervisor",
                "iteration": iterations,
                "next": decision.next,
                "instructions": decision.instructions,
            }
        ]
        if decision.draft:
            out["draft"] = decision.draft
        if decision.next == "finish":
            out["final_answer"] = decision.final_answer or draft
        # 运行监测：记录主管节点的输入上下文与最终结构化决策
        out["debug"] = {"input": context, "output": decision.model_dump()}
        return out

    return node


def make_emergency_synthesizer_node(
    model: BaseChatModel,
) -> Callable[[AgentState], dict[str, Any]]:
    """紧急综合节点：只调用一次，产出带置信度的阶段快报。"""

    def node(state: AgentState) -> dict[str, Any]:
        payload = {
            "question": state["question"],
            "findings": state.get("findings", []),
            "analysis": state.get("analysis", []),
            "draft": state.get("draft", ""),
            "feedback": state.get("feedback", []),
            "review": state.get("review"),
        }
        messages = [
            SystemMessage(content=EMERGENCY_SYNTHESIS_PROMPT),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
        ]
        report = invoke_structured(model, EmergencyReport, messages)
        trace_entry = {"node": "emergency_synthesizer", "confidence": report.confidence}
        return {
            "emergency_report": report.model_dump(),
            "trace": [trace_entry],
            "debug": {"input": payload, "output": report.model_dump()},
        }

    return node


def make_worker_node(
    model: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str,
    out_key: str,
) -> Callable[[AgentState], dict[str, Any]]:
    """用 create_react_agent 构造 Worker 子图：模型自主决定调工具、调几次，直到自己收手。"""
    agent = create_react_agent(model, tools, prompt=SystemMessage(content=system_prompt))

    def node(state: AgentState) -> dict[str, Any]:
        instructions = state.get("task_instructions") or ""
        prompt = state["question"]
        if instructions:
            prompt = f"用户问题：{state['question']}\n主管指令：{instructions}"
        try:
            result = agent.invoke(
                {"messages": [HumanMessage(content=prompt)]},
                config={"recursion_limit": 8},
            )
        except Exception as exc:  # noqa: BLE001 - ReAct 超步数/超时兜底
            items = [{"summary": f"Worker 执行受限: {str(exc)[:120]}", "chunk_id": None, "source": None}]
            return {
                out_key: items,
                "messages": [],
                "worker_report": {
                    "self_check": "failed",
                    "error": str(exc)[:200],
                    "next_suggestion": "",
                },
                "debug": {
                    "input": prompt,
                    "output": None,
                    "log": [],
                    "error": str(exc)[:200],
                },
            }
        last = result["messages"][-1]
        text = last.content if isinstance(last.content, str) else str(last.content)
        data = _extract_json(text)
        if isinstance(data, dict) and isinstance(data.get("findings"), list):
            # 新格式：{"findings": [...], "self_check": ..., "next_suggestion": ...}
            items = [d for d in data["findings"] if isinstance(d, dict)]
            report = {
                "self_check": data.get("self_check", "ok"),
                "error": data.get("error", ""),
                "next_suggestion": data.get("next_suggestion", ""),
            }
        elif isinstance(data, list):
            # 兼容旧格式：纯 JSON 数组
            items = [d for d in data if isinstance(d, dict)]
            report = {"self_check": "ok", "error": "", "next_suggestion": ""}
        else:
            items = [{"summary": text, "chunk_id": None, "source": None}]
            report = {"self_check": "partial", "error": "输出无法解析", "next_suggestion": ""}
        return {
            out_key: items,
            "messages": result["messages"],
            "worker_report": report,
            "debug": {
                "input": prompt,
                "output": {"findings": items, "worker_report": report},
                "log": _serialize_messages(result["messages"]),
            },
        }

    return node


def make_reviewer_node(model: BaseChatModel) -> Callable[[AgentState], dict[str, Any]]:
    def node(state: AgentState) -> dict[str, Any]:
        payload = {
            "question": state["question"],
            "draft": state.get("draft", ""),
            "findings": state.get("findings", []),
            "analysis": state.get("analysis", []),
        }
        messages = [
            SystemMessage(content=REVIEWER_PROMPT),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
        ]
        verdict = invoke_structured(model, ReviewVerdict, messages)
        review = verdict.model_dump()
        if verdict.verdict == "pass" and verdict.revised_report:
            review["revised_report"] = verdict.revised_report
        trace_entry = {"node": "reviewer", "verdict": verdict.verdict, "feedback": verdict.feedback}
        return {
            "review": review,
            "trace": [trace_entry],
            "debug": {"input": payload, "output": review},
        }

    return node
