# Multi-Agent RAG Supervisor

一个基于 **LangGraph Supervisor 模式**的多 Agent 协作 + RAG 系统骨架，产品场景是**「连锁奶茶店运营助手」**。

## 产品场景

**给谁用**：连锁奶茶店的区域运营人员（管着十几家门店、同时接入美团/饿了么/抖音团购三个平台）。

**解决什么实际问题**：运营每天要回答「退款政策是什么」「华东区门店卖了多少」「退款率为什么高」「鲜奶效期预警了怎么处理」这类问题——平台规则、食安手册、门店数据散在三个地方，规则之间还会冲突（平台退款政策 vs 门店成本账 vs 食安红线）。这个系统让运营用自然语言提问，Supervisor 自动判断问题类型，从角色池中调度专家：

- 文档/规则类问题（平台合作规则、食品安全手册、门店运营手册）→ `rag_researcher` 检索知识库并核验引用；
- 数据/统计类问题 → `sql_analyst` 查询只读门店订单数据库；
- 库存/缺货/效期问题 → `stock_analyst` 查询物料库存表；
- 最终产出**带数据出处和文档引用**的分析报告，`reviewer` 质检后交付。

这个项目的核心目的：让你能对着面试官讲清楚——**什么是 Agent、为什么它不是 Workflow、多 Agent 怎么协作、RAG 怎么被 Agent 使用、这套系统怎么评估**。

## 系统架构

- **Supervisor 主管**：读全局状态，从角色池中动态选择专家 / 是否收工（LLM 结构化决策）
- **rag_researcher（角色池）**：检索知识库并核验引用，处理文档类问题（ReAct 子图）
- **sql_analyst（角色池）**：查询只读门店订单数据库，处理数据类问题（ReAct 子图）
- **web_searcher（角色池）**：搜索外部公开网页，处理需要联网调研的问题（ReAct 子图）
- **stock_analyst（角色池）**：查询物料库存表，处理库存 / 缺货 / 补货 / 效期问题（ReAct 子图）
- **Reviewer 审查员**：质检报告（覆盖度 / 引用真实性 / 幻觉），不合格打回

流程：用户提问 → Supervisor 判断问题类型 → 从角色池选择专家 → 专家执行（ReAct 循环）→ Supervisor 汇总草稿 → Reviewer 质检 → 不合格打回、合格交付。**所有 Worker 和 Reviewer 都回到 Supervisor，构成自主循环，而不是一条流水线。**

## 角色池设计（动态选择，而不是自由生成）

角色由代码预定义（名称、能力描述、提示词、工具集），Supervisor 在运行时只能**从池中选**，不能凭空生成新角色：

- 白名单校验：Supervisor 输出不在 `{角色池} ∪ {reviewer, finish}` 内时，代码强制回退到默认专家；
- 工具白名单：每个角色只能使用注册表中声明的工具（`sql_analyst` 只有只读 SELECT 工具）；
- 最大轮次硬控：达到上限强制收尾，防止无限循环。

想扩展能力时，往 `app/orchestration/registry.py` 的角色池里加一条 `WorkerSpec` 即可——这就是「能力扩展性」的落点。

`web_searcher` 需要网络搜索能力：配置 `TAVILY_API_KEY` 时走 Tavily，否则回退 DuckDuckGo；
两者都不可用时工具会返回明确错误，Supervisor 可以转派其他专家，而不是让 Agent 硬编。

## 多 Agent 协作细节（对照《AI Agents in Depth》第 10 章）

- **任务自包含**：Worker 收到的不是裸问题，而是「用户问题 + 主管指令」的任务包——避免主管失明导致的「专家看不到指令就乱干」；
- **主管上下文瘦身**：Supervisor 只接收 findings/analysis 的**结论摘要**和草稿前 500 字，不看过程全量——防止上下文膨胀和思维惯性传染；
- **分角色模型**：`SUPERVISOR_MODEL` / `WORKER_MODEL` 可分开配置——把更强的模型给规划者（主管是瓶颈），Worker 用轻量模型省成本；
- **Worker 自检与移交建议**：Worker 输出带 `self_check / error / next_suggestion`，Supervisor 决策时参考——相当于手写的显式移交，工具失败时能快速转派而不浪费轮次；
- **验证节点**：Reviewer 质检 + 无 LLM 的 guardrail 门控，阻断错误级联（错误从研究员一路传到报告是经典失败模式）。

## 为什么这是 Agent 而不是 Workflow

- **控制权归属**：下一步去哪由 Supervisor（LLM）在运行时决定，不是代码里写死的 if/else
- **有自主循环**：Supervisor → Worker → Supervisor 循环，直到模型自己判定 finish
- **路径是生成的**：同一问题跑多次可能走不同路径（检索几次、要不要核验、要不要打回重做都是动态的）
- **Worker 内部也是 Agent**：Researcher / Analyst 是 ReAct 循环，模型自己决定调哪个工具、调几次
- **出错能自我修正**：Reviewer 打回 → Supervisor 带着反馈重新分派，而不是固定错误分支

对比：如果把流程画成固定顺序、每个节点只做一次调用，那就是 Workflow——也是本项目刻意避免的写法。

## 快速开始

```bash
pip install -r requirements.txt

python main.py build-kb --provider mock
python main.py build-db
python main.py mock "已支付但未开始制作的订单多久内可以申请退款？" --max-iterations 4
python main.py mock "2026年第一季度整体退款率是多少？" --max-iterations 4
python eval/evaluate.py --provider mock --max-iterations 4
```

`build-db` 会生成一个示例只读门店订单数据库（`data/db/orders.db`），供 `sql_analyst` / `stock_analyst` 使用；`ask` 命令在真实模型下会根据问题类型自动选择专家。

## Web 前端（演示展示型 v1）

前端在 `web/`（React 18 + Vite + TypeScript + Tailwind），五个页面：

- `/ask` 问答演示：实时执行图（节点点亮/脉冲）+ 时间线 + Markdown 答案引用溯源 + 回放/历史；
- `/eval` 评估看板：8 项指标卡 + 历史报告列表 + 「运行评估」（SSE 逐用例进度，完成自动刷新）；
- `/kb` 知识库管理：文档上传/删除/预览、重建向量库（逐文件进度条）、检索测试台（top-k + 引用核验徽标）；
- `/arch` 架构讲解：角色池卡片 + Agent vs Workflow 对比 + 降级质量闭环（verified/partial/failed）。
- `/monitor` 数据监测：单次调用的完整 Agent 思考过程——主管每轮决策、专家工具调用参数与返回结果、质检判定、门控拦截（进程内保存最近 50 次运行）。

启动方式（两个终端）：

```bash
# 终端 1：后端 API（:8000）；若 web/dist 已构建，同一端口还会托管前端静态资源
python main.py serve --port 8000

# 终端 2：前端 dev（:5173，/api 自动代理到 :8000）
cd web && npm install && npm run dev
```

无 key 演示：问答页/评估页的 provider 选 `mock` 即可跑通全流程；
知识库上传文档后点「重建向量库」生效，检索测试台可现场验证引用核验。
前后端接口契约（路径、SSE 事件字段、TS 类型）见 `CONTRACT.md`。

## 配置真实模型

**配置 API key 的方式（两种任选）：**

1. **推荐：`.env` 文件**——复制 `.env.example` 为项目根目录的 `.env`，填上 key 即可（项目启动时自动加载，`.env` 已被 .gitignore 忽略，不会提交泄露）：

   ```bash
   # 复制后编辑 .env，填入你的 key
   LLM_PROVIDER=minimax
   MINIMAX_API_KEY=sk-你的key
   ```

2. **环境变量**——在终端设置（仅当前会话生效）：

   ```powershell
   $env:LLM_PROVIDER="minimax"
   $env:MINIMAX_API_KEY="sk-你的key"
   ```

| provider | 说明 |
|---|---|
| openai | 设置 OPENAI_API_KEY、OPENAI_MODEL（默认 gpt-4o-mini）、EMBEDDING_MODEL |
| ollama | 本地启动 Ollama，走 OpenAI 兼容端点：OLLAMA_MODEL（默认 qwen2.5:7b）、OLLAMA_BASE_URL |
| minimax | 推荐：一个 key 全搞定。MINIMAX_API_KEY + MiniMax-Text-01（chat）+ embo-01（embedding），国内端点 api.minimaxi.com/v1 |
| deepseek | DEEPSEEK_API_KEY + deepseek-v4-flash；官方无 embedding API，向量化默认走本地 Ollama nomic-embed-text |
| mock | 无 key 也能跑：FakeEmbeddings + 剧本化假模型，用于验证图结构和流程 |

复合任务（多专家接力）建议把 `MAX_ITERATIONS` 调到 6，给「查数据 → 查规则 → 质检 → 交付」留出轮次；默认 4 只够简单问答。

示例（Ollama）：

```bash
$env:LLM_PROVIDER="ollama"
python main.py build-kb
python main.py ask "总结一下门店的退款政策"
```

示例（MiniMax，推荐）：

```bash
$env:LLM_PROVIDER="minimax"
$env:MINIMAX_API_KEY="你的key"
python main.py build-kb
python main.py ask "2026年第一季度华东区门店的订单量和退款率是多少？"
```

## 目录结构

```text
agent-rag-supervisor/
├── main.py                 # CLI：build-kb / build-db / ask / mock / serve
├── CONTRACT.md             # 前后端接口契约（v1 锁定版）
├── app/
│   ├── api/                       # HTTP API（按业务域拆 routers/）
│   ├── core/                      # 配置 / 嵌入
│   │   ├── config.py             # 模型与运行配置
│   │   └── embeddings.py         # Embeddings 适配层
│   ├── orchestration/            # 多智能体编排
│   │   ├── state.py              # 图共享状态
│   │   ├── registry.py           # 角色池（可扩展 WorkerSpec）
│   │   ├── guardrail.py          # 守门员节点
│   │   ├── agents.py             # Supervisor / Reviewer 节点 + Worker 工厂
│   │   ├── graph.py              # LangGraph 图组装
│   │   └── tools.py              # Agent 工具（KB / SQL / code）
│   ├── knowledge/                  # RAG / 知识库
│   │   ├── rag.py                # 向量检索 + 引用核验
│   │   └── kb_service.py         # 知识库文档管理（上传/删除/重建编排）
│   └── observability/              # 运行监控
│       └── monitor.py              # 追踪每轮运行的 trace 步骤
├── eval/
│   ├── cases.json          # 分级评估集
│   └── evaluate.py         # 评估脚本 + 指标报告
├── web/                    # React 前端（演示展示型 v1）
├── tests/                  # 后端 API 契约测试（pytest）
├── data/kb/                # 示例知识库（Markdown）
├── data/db/                # 示例门店订单数据库（build-db 生成）
└── storage/chroma/         # 向量库持久化（运行时生成）
```

## 评估体系

按《AI Agents in Depth》第 6 章的方法论搭建评估台（四件套：**任务集 + 运行器 + 评判器 + 指标**）：

**任务集**（`eval/cases.json`，23 个用例，防泄漏：数据/文档都是本项目定制，模型训练数据中不存在）：

- 正常任务（normal）：该检索就检索、该查库就查库，覆盖四类专家；
- 边界任务（boundary）：闲聊等不该调度专家的场景，测「不该调工具就别调」；
- 陷阱任务（trap）：知识库/数据库里不存在的内容，测诚实性（禁止编造）。
- 复合任务（composite）：E20-E22 需要多专家接力（先查数据/库存、再查规则、最后综合），测 Supervisor 的跨轮调度与多源综合能力；
- 食安任务：E23 覆盖食品安全手册（效期预警、投诉响应），测「规则冲突 + 合规红线」场景下的检索与裁决；

**评判器**（`eval/judge.py`，LLM-as-a-Judge）：裁判模型按 Rubric（正确性 / 工具使用 / 诚实性）打 0-5 分，强制 JSON 输出，`--judge` 启用。

**指标**（质量 + 过程）：

- 任务成功率：最终报告是否覆盖必备关键词；
- 工具调用正确率：实际派发的专家是否匹配用例的 `expected_workers`；
- 平均迭代轮数 / 平均工具调用次数 / 平均 token / 平均耗时：过程与成本指标；
- 审查打回率 / 降级触发率 / 降级交付率 / 诚实失败率 / 门控拦截次数：质检环与降级闭环指标。

**消融与模型替换**（`eval/ablation.py`）：同一评估集跑 `full / no_reviewer / no_guardrail` 三个变体，
分数大跌的组件就是关键（去掉 Reviewer 后成功率明显下降）；换模型重跑即可区分「模型瓶颈」和「Harness 瓶颈」。

运行方式：

```bash
python eval/evaluate.py --limit 3                 # 真实模型跑前 3 个用例
python eval/evaluate.py --limit 1 --judge         # 启用 LLM-as-a-Judge 打分
python eval/ablation.py --limit 5                 # 消融实验
```

注意：mock 模式只用于验证脚本和图结构，指标数字没有参考意义；真实评估在 minimax / deepseek / openai / ollama 下运行。

## 降级质量闭环

轮次耗尽时系统**不交半成品**，而是走两条强制路径（由代码路由触发，不依赖模型自觉）：

```text
supervisor --review pass--> finish（quality=verified 正常交付）
supervisor --轮次耗尽--> emergency_synthesizer --> guardrail --> END
```

- `emergency_synthesizer`：只调用一次，产出带置信度标注的 `EmergencyReport`（已确认事实 / 初步洞察 / 需后续核实 / confidence）；
- `guardrail`：**无 LLM 的规则门控**，三关校验——结构完整性（三区块齐全）、引用真实性（chunk_id 必须能在 findings 中找到）、诚实度（confidence 存在且 ≤1）；
  - 通过 → `quality=partial`，输出带「阶段性快报」声明的 Markdown；
  - 不通过 → `quality=failed`，诚实告知原因并附已有发现，绝不硬编答案。

验证方式：`python main.py mock "问题" --max-iterations 0` 可强制触发降级路径；`eval/evaluate.py --max-iterations 1` 可批量测降级指标。

## 面试怎么讲这个项目

- 先用「Agent vs Workflow 判断标准」开场，再拿本项目当例证
- 讲 Supervisor 模式时，画出「循环」而不是「流水线」
- 讲 RAG 时强调「检索是 Agent 的工具，不是固定的前置步骤」
- 讲评估时准备 bad case 故事：引用编造 → Reviewer 打回 → 修复后打回率下降
- 讲场景选型时主动说明：为什么是连锁门店而不是纯电商——平台规则、食安合规、门店数据三方冲突，
  让 Supervisor 的「裁决」和 Reviewer/Guardrail 的「否决」成为业务必要而非装饰
- 讲角色池时主动说出「动态选择 vs 自由生成」的取舍：自由生成不可控（安全边界、评估、成本全崩），
  所以用「预注册角色 + 运行时选择 + 白名单校验」——这比无脑上动态生成更能体现架构判断力
