// 前后端协作契约（CONTRACT.md 第 4 节）的 TS 镜像，字段与后端严格一致，禁止私自增改。

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

export interface MonitorMessage {
  role: string;
  content: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  name?: string;
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
