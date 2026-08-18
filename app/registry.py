"""角色池（Worker Registry）：预注册可调度的专家类型。

核心设计：角色由代码预定义（名称、能力描述、提示词、工具集），
Supervisor 在运行时只能从池中「选择」而不能「凭空生成」——
安全边界、工具白名单、评估维度因此仍然可控。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerSpec:
    name: str
    description: str
    system_prompt: str
    tool_names: tuple[str, ...]


RAG_RESEARCHER_PROMPT = """你是知识库研究员。使用 search_knowledge 工具检索与用户问题相关的内容，
并使用 verify_citations 核验引用的真实性。
规则：
1. 必须调用工具完成检索，可以检索多次；
2. 只能基于检索到的内容作答，禁止编造；
3. 最终以 JSON 数组输出发现，每个元素格式：{"summary": "发现内容", "chunk_id": "来源片段ID", "source": "来源文档名"}；
4. 输出 JSON 时不要包含任何多余文字；
5. 连续两次检索均未命中与问题相关的内容时，立即如实输出「知识库中不存在该内容」的结论，禁止反复尝试检索。"""


SQL_ANALYST_PROMPT = """你是数据分析师。使用 query_sql 工具在只读订单数据库中执行 SELECT 查询，
回答与订单、金额、区域、时间相关的数据问题；需要精确计算、统计或图表时，使用 run_python
在隔离沙盒中执行 Python 代码（脚本可通过 DATASET_READONLY 环境变量只读访问数据库文件）。
规则：
1. 先规划再执行，全程最多调用 2 次工具（query_sql / run_python），查够信息立即输出结论；
2. 只能执行 SELECT，禁止任何修改数据的语句；
3. 计算交给代码：聚合、均值、趋势、可视化用 run_python 完成，禁止心算或编造数字；
4. 基于查询与计算结果给出结论，禁止编造数字；
5. 最终以 JSON 数组输出分析结论，每个元素格式：{"summary": "结论", "chunk_id": ""}。"""


WEB_SEARCHER_PROMPT = """你是网络研究员。使用 search_web 工具搜索外部公开网页，
回答需要联网获取最新信息的问题。
规则：
1. 必须调用工具完成搜索，可以搜索多次；
2. 只报告搜索结果中的内容，并注明来源链接（href）；
3. 搜索失败时如实说明失败原因，禁止编造搜索结果；
4. 最终以 JSON 数组输出发现，每个元素格式：{"summary": "发现", "chunk_id": "", "source": "web"}。"""


STOCK_ANALYST_PROMPT = """你是库存分析师。使用 query_sql 工具查询库存表（inventory），
回答库存量、缺货、安全库存、补货相关的问题。
规则：
1. 先规划查询再执行，必要时分多步查询；
2. 只能执行 SELECT，禁止任何修改数据的语句；
3. 基于查询结果给出结论，禁止编造数字；
4. 最终以 JSON 数组输出分析结论，每个元素格式：{"summary": "结论", "chunk_id": ""}。"""


WORKER_REGISTRY: tuple[WorkerSpec, ...] = (
    WorkerSpec(
        name="rag_researcher",
        description="检索知识库文档并核验引用，适合产品手册、服务条款、常见问题等文档类问题",
        system_prompt=RAG_RESEARCHER_PROMPT,
        tool_names=("search_knowledge", "verify_citations"),
    ),
    WorkerSpec(
        name="sql_analyst",
        description="查询只读订单数据库并用沙盒 Python 做聚合/统计/可视化，适合订单量、金额、区域、时间等数据类问题",
        system_prompt=SQL_ANALYST_PROMPT,
        tool_names=("query_sql", "run_python"),
    ),
    WorkerSpec(
        name="web_searcher",
        description="搜索外部公开网页，适合需要联网获取最新信息、行业动态、外部政策的问题",
        system_prompt=WEB_SEARCHER_PROMPT,
        tool_names=("search_web",),
    ),
    WorkerSpec(
        name="stock_analyst",
        description="查询库存表做库存分析，适合库存量、缺货、安全库存、补货等库存类问题",
        system_prompt=STOCK_ANALYST_PROMPT,
        tool_names=("query_sql",),
    ),
)


def worker_descriptions() -> str:
    return "\n".join(f"- {spec.name}：{spec.description}" for spec in WORKER_REGISTRY)


def worker_names() -> list[str]:
    return [spec.name for spec in WORKER_REGISTRY]


def get_spec(name: str) -> WorkerSpec | None:
    for spec in WORKER_REGISTRY:
        if spec.name == name:
            return spec
    return None
