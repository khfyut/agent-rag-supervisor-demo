# 前后端协作契约（v1 锁定版）

本文件是子 agent 协作的**唯一契约**。接口路径、SSE 事件字段、TS 类型一律以本文件为准。
任何变更必须先经 root 批准；子 agent 不得单方修改。

## 1. 目录与文件所有权

| 负责人 | 范围 |
|---|---|
| root | `CONTRACT.md`、最终路由接线（`App.tsx` / router）、跨模块整合修复、端到端验收 |
| 子 agent A | `main.py`、`app/rag.py`、`app/api.py`（新增）、`app/kb_service.py`（新增）、`requirements.txt`、后端 `tests/` |
| 子 agent B | `web/` 脚手架与共享层：`package.json`、`vite.config.ts`、`tsconfig*.json`、Tailwind/PostCSS 配置、`index.html`、`src/main.tsx`、`src/App.tsx`、`src/types.ts`、`src/api/*`、`src/store/*`、`src/components/*`、`src/pages/AskPage.tsx`、`src/data/presetQuestions.ts`、前端测试 |
| 子 agent C | 仅 `src/pages/EvalPage.tsx`、`src/pages/KbPage.tsx`、`src/pages/ArchPage.tsx` 及页面局部文件（如 `src/pages/eval/`、`src/pages/kb/`、`src/pages/arch/`、自建 mock 适配） |

禁止互相修改对方所有权内的文件。若共享类型/组件尚未就绪，C 可在自己目录内定义
局部类型/局部组件（文件名以 `local` 前缀标注），并在文件头注释「integration: 切换到共享类型/组件」，
由 root 在整合阶段统一替换。

## 2. 后端接口清单（FastAPI，挂载在 `app/api.py`，前缀 `/api`）

| 方法 | 路径 | 请求体 | 响应 |
|---|---|---|---|
| POST | `/api/ask` | `{question: str, provider?: str\|null, max_iterations?: int\|null}` | SSE（问答事件） |
| GET | `/api/workers` | - | `[{name, description, tool_names: str[]}]` |
| GET | `/api/status` | - | `{provider, model, kb_ready, db_ready, kb_chunks: int\|null, reports_count: int}` |
| GET | `/api/kb/docs` | - | `{docs: KbDoc[], dirty: bool}` |
| GET | `/api/kb/docs/{filename}` | - | `{name, content}`（404 时 `{detail}`） |
| POST | `/api/kb/docs` | multipart，字段名 `file` | `{docs: KbDoc[], dirty: true}` |
| DELETE | `/api/kb/docs/{filename}` | - | `{docs: KbDoc[], dirty: true}` |
| POST | `/api/kb/rebuild` | - | SSE（重建事件） |
| POST | `/api/kb/search` | `{query: str, k?: int}`（k 默认 4，范围 1–8） | `{results: KbSearchResult[]}` |
| GET | `/api/eval/reports` | - | `{reports: EvalReportMeta[]}`（按生成时间倒序） |
| GET | `/api/eval/reports/{filename}` | - | `EvalReport`（404 时 `{detail}`） |
| POST | `/api/eval/run` | `{provider?: str\|null, limit?: int\|null, max_iterations?: int\|null}` | SSE（评估事件） |
| GET | `/api/monitor/runs` | - | `{runs: MonitorRunMeta[]}`（进程内最近 50 次问答，倒序） |
| GET | `/api/monitor/runs/{run_id}` | - | `MonitorRun`（404 时 `{detail}`） |

通用规则：
- 全站响应与事件数据均为 UTF-8 JSON；SSE 用 `text/event-stream`，格式
  `event: <name>\ndata: <json>\n\n`。
- `provider` 取值：`openai | ollama | deepseek | minimax | mock | null`；null/缺省走 `.env` 的 `LLM_PROVIDER`。
- KB 文档规则：仅 `.md` / `.txt`，单文件 ≤ 1MB，文件名只取 basename，服务端必须做路径穿越校验；
  上传/删除后 `dirty=true`，重建成功后 `dirty=false`（进程内状态即可）。
- `POST /api/ask`、`POST /api/kb/rebuild`、`POST /api/eval/run` 均为 SSE；出错时先发对应 `*_error` 事件再结束流。

## 3. SSE 事件协议

### 3.1 问答 `/api/ask`

| 事件名 | data 字段 |
|---|---|
| `run_start` | `{run_id: str, question: str}` |
| `supervisor` | `{iteration: int, next: str, instructions: str}` |
| `worker` | `{worker: str, findings: Finding[], tool_calls: ToolCall[], self_check: str, error: str}` |
| `reviewer` | `{verdict: "pass"\|"fail", feedback: str}` |
| `emergency` | `{report: EmergencyReport, confidence: number}` |
| `guardrail` | `{passed: bool, quality: str, reason: str}` |
| `done` | `{final_answer: str, quality: str, finish_reason: str, iterations: int, trace: TraceEntry[], findings: Finding[], analysis: Finding[], emergency_report: EmergencyReport\|null, guardrail: GuardrailResult\|null}` |
| `error` | `{message: str}` |

实现要求：`graph.stream(stream_mode="updates")` 逐节点产出；`worker` 事件的 `tool_calls`
从该节点返回的 `messages` 中提取（AIMessage.tool_calls → `{name, args}`）。

### 3.2 重建 `/api/kb/rebuild`

| 事件名 | data 字段 |
|---|---|
| `kb_build_start` | `{total_files: int}` |
| `kb_build_file` | `{current: int, total: int, filename: str, chunks: int}` |
| `kb_build_done` | `{total_docs: int, total_chunks: int, collection_count: int}` |
| `kb_build_error` | `{message: str}` |

### 3.3 评估 `/api/eval/run`

| 事件名 | data 字段 |
|---|---|
| `eval_start` | `{total: int}` |
| `eval_case` | `{index: int, id: str, level: str, success: bool, missing_keywords: str[]}` |
| `eval_done` | `{report: EvalReport, filename: str}` |
| `eval_error` | `{message: str}` |

## 4. TS 共享类型（`web/src/types.ts`，B 实现，C 只读引用）

```ts
export interface WorkerSpec {
  name: string;
  description: string;
  tool_names: string[];
}

export interface SystemStatus {
  provider: string;
  model: string;
  kb_ready: boolean;
  db_ready: boolean;
  kb_chunks: number | null;
  reports_count: number;
}

export interface Finding {
  summary: string;
  chunk_id?: string | null;
  source?: string | null;
}

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
}

export interface Fact {
  statement: string;
  chunk_id: string;
}

export interface EmergencyReport {
  summary: string;
  confirmed_facts: Fact[];
  insights: string[];
  to_verify: string[];
  confidence: number;
}

export interface GuardrailResult {
  passed: boolean;
  quality: string;
  reason: string;
}

export interface TraceEntry {
  node: string;
  iteration?: number;
  next?: string;
  instructions?: string;
  verdict?: string;
  feedback?: string;
  confidence?: number;
  passed?: boolean;
  quality?: string;
  reason?: string;
}

export type AskEvent =
  | { type: "run_start"; run_id: string; question: string }
  | { type: "supervisor"; iteration: number; next: string; instructions: string }
  | { type: "worker"; worker: string; findings: Finding[]; tool_calls: ToolCall[]; self_check: string; error: string }
  | { type: "reviewer"; verdict: "pass" | "fail"; feedback: string }
  | { type: "emergency"; report: EmergencyReport; confidence: number }
  | { type: "guardrail"; passed: boolean; quality: string; reason: string }
  | { type: "done"; final_answer: string; quality: string; finish_reason: string; iterations: number; trace: TraceEntry[]; findings: Finding[]; analysis: Finding[]; emergency_report: EmergencyReport | null; guardrail: GuardrailResult | null }
  | { type: "error"; message: string };

export interface KbDoc {
  name: string;
  size: number;
  modified_at: string;
  chunk_count: number | null;
}

export interface KbSearchResult {
  content: string;
  source: string;
  chunk_id: string;
  score: number;
  citation_valid: boolean;
}

export type KbBuildEvent =
  | { type: "kb_build_start"; total_files: number }
  | { type: "kb_build_file"; current: number; total: number; filename: string; chunks: number }
  | { type: "kb_build_done"; total_docs: number; total_chunks: number; collection_count: number }
  | { type: "kb_build_error"; message: string };

export interface EvalReportMeta {
  filename: string;
  generated_at: string;
  provider: string;
  model: string;
  total_cases: number;
  task_success_rate: number;
  reviewer_pass_rate: number;
  avg_iterations: number;
  avg_elapsed_s: number;
  degradation_rate: number;
  degradation_delivery_rate: number;
  honest_failure_rate: number;
  hallucination_blocked: number;
}

export interface EvalCaseResult {
  id: string;
  level: string;
  success: boolean;
  keywords_hit: string[];
  missing_keywords: string[];
  iterations: number;
  elapsed_s: number;
  citations: string[];
  citation_valid: boolean;
  reviewer_verdicts: string[];
  final_answer: string;
  quality: string;
  finish_reason: string;
  guardrail_reason: string;
}

export interface EvalReport extends EvalReportMeta {
  cases: EvalCaseResult[];
}

export type EvalEvent =
  | { type: "eval_start"; total: number }
  | { type: "eval_case"; index: number; id: string; level: string; success: boolean; missing_keywords: string[] }
  | { type: "eval_done"; report: EvalReport; filename: string }
  | { type: "eval_error"; message: string };

export interface MonitorToolCall {
  name: string;
  args: Record<string, unknown>;
  result?: string | null;
}

export interface MonitorStep {
  node: string;
  worker?: string;
  iteration?: number;
  next?: string;
  instructions?: string;
  input?: unknown;
  output?: unknown;
  log?: MonitorMessage[];
  tool_calls?: MonitorToolCall[];
  findings?: Finding[];
  self_check?: string;
  error?: string;
  verdict?: string;
  feedback?: string;
  report?: EmergencyReport;
  confidence?: number;
  passed?: boolean;
  quality?: string;
  reason?: string;
}

export interface MonitorMessage {
  role: string;
  content: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  name?: string;
}

export interface MonitorRunMeta {
  run_id: string;
  question: string;
  provider: string;
  created_at: string;
  status: "running" | "done" | "error";
  iterations: number;
  quality: string;
  finish_reason: string;
}

export interface MonitorRun extends MonitorRunMeta {
  final_answer: string;
  error: string;
  steps: MonitorStep[];
  trace: TraceEntry[];
}
```

## 5. 约定

- 全项目 UTF-8 编码；代码注释用中文；前端 UI 全中文。
- mock provider 用于无 key 演示与测试；`python main.py mock "问题"` 现有行为保持不变。
- `main.py` 新增 `serve` 子命令：`python main.py serve --port 8000`，其余 CLI 命令不动。
- `requirements.txt` 增加 `fastapi`、`uvicorn`；dev 依赖 `pytest`、`httpx`（已装）。
- 前端 dev：Vite :5173，`vite.config.ts` 配置 `server.proxy` 将 `/api` 转发到 `http://localhost:8000`；
  生产模式 FastAPI 挂载 `web/dist` 静态资源。
