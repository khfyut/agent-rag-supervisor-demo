// integration: 页面测试专用 mock 数据；共享层就绪后仍可保留用于组件测试。

import type {
  EvalEvent,
  EvalReport,
  EvalReportMeta,
  KbBuildEvent,
  KbDoc,
  KbSearchResult,
  SystemStatus,
  WorkerSpec,
} from "../../types";

export const MOCK_STATUS: SystemStatus = {
  provider: "mock",
  model: "gpt-4o-mini",
  kb_ready: true,
  db_ready: true,
  kb_chunks: 12,
  reports_count: 3,
};

export const MOCK_WORKERS: WorkerSpec[] = [
  {
    name: "rag_researcher",
    description: "检索知识库文档并核验引用，适合产品手册、服务条款、常见问题等文档类问题",
    tool_names: ["search_knowledge", "verify_citations"],
  },
  {
    name: "sql_analyst",
    description: "查询只读订单数据库做数据分析，适合订单量、金额、区域、时间等数据类问题",
    tool_names: ["query_sql"],
  },
  {
    name: "web_searcher",
    description: "搜索外部公开网页，适合需要联网获取最新信息、行业动态、外部政策的问题",
    tool_names: ["search_web"],
  },
  {
    name: "stock_analyst",
    description: "查询库存表做库存分析，适合库存量、缺货、安全库存、补货等库存类问题",
    tool_names: ["query_sql"],
  },
];

export const MOCK_DOCS: KbDoc[] = [
  { name: "平台合作规则.md", size: 4120, modified_at: "2026-08-01T10:00:00", chunk_count: 4 },
  { name: "食品安全手册.md", size: 3960, modified_at: "2026-08-02T11:30:00", chunk_count: 4 },
  { name: "门店运营手册.md", size: 4180, modified_at: "2026-08-03T09:15:00", chunk_count: 4 },
];

export const MOCK_SEARCH_RESULTS: KbSearchResult[] = [
  {
    content: "已支付但未开始制作的订单，可在支付后 30 分钟内申请全额退款，系统自动审核通过。",
    source: "平台合作规则.md",
    chunk_id: "平台合作规则.md#1",
    score: 0.912,
    citation_valid: true,
  },
  {
    content: "食材剩余保质期不足 48 小时时，系统自动推送效期预警，门店需立即下架相关产品并停止使用。",
    source: "食品安全手册.md",
    chunk_id: "食品安全手册.md#2",
    score: 0.731,
    citation_valid: true,
  },
  {
    content: "量子引力理论在奶茶配方优化中的应用属于伪命题，知识库中不存在该内容。",
    source: "门店运营手册.md",
    chunk_id: "门店运营手册.md#99",
    score: 0.402,
    citation_valid: false,
  },
];

export const MOCK_REPORTS_META: EvalReportMeta[] = [
  {
    filename: "report_20260814_151708.json",
    generated_at: "2026-08-14T15:17:08",
    provider: "mock",
    model: "gpt-4o-mini",
    total_cases: 23,
    task_success_rate: 0.4,
    reviewer_pass_rate: 1.0,
    avg_iterations: 3.0,
    avg_elapsed_s: 0.12,
    degradation_rate: 0.1,
    degradation_delivery_rate: 0.5,
    honest_failure_rate: 0.05,
    hallucination_blocked: 2,
  },
  {
    filename: "report_20260814_143625.json",
    generated_at: "2026-08-14T14:36:25",
    provider: "mock",
    model: "gpt-4o-mini",
    total_cases: 7,
    task_success_rate: 0.1429,
    reviewer_pass_rate: 1.0,
    avg_iterations: 3.0,
    avg_elapsed_s: 0.01,
    degradation_rate: 0,
    degradation_delivery_rate: 0,
    honest_failure_rate: 0,
    hallucination_blocked: 0,
  },
];

export function buildMockReport(): EvalReport {
  const meta = MOCK_REPORTS_META[0];
  return {
    ...meta,
    cases: [
      {
        id: "E1",
        level: "simple",
        success: true,
        keywords_hit: ["30分钟"],
        missing_keywords: [],
        iterations: 3,
        elapsed_s: 0.11,
        citations: ["平台合作规则.md#1"],
        citation_valid: true,
        reviewer_verdicts: ["pass"],
        final_answer: "已支付但未开始制作的订单，可在支付后 30 分钟内申请全额退款。",
        quality: "verified",
        finish_reason: "review_pass",
        guardrail_reason: "",
      },
      {
        id: "E9",
        level: "hard",
        success: false,
        keywords_hit: [],
        missing_keywords: ["量子引力"],
        iterations: 4,
        elapsed_s: 0.2,
        citations: [],
        citation_valid: false,
        reviewer_verdicts: ["fail", "pass"],
        final_answer: "知识库中不存在量子引力理论相关内容，无法回答。",
        quality: "verified",
        finish_reason: "review_pass",
        guardrail_reason: "",
      },
    ],
  };
}

export const MOCK_EVAL_EVENTS: EvalEvent[] = [
  { type: "eval_start", total: 2 },
  {
    type: "eval_case",
    index: 0,
    id: "E1",
    level: "simple",
    success: true,
    missing_keywords: [],
  },
  {
    type: "eval_case",
    index: 1,
    id: "E9",
    level: "hard",
    success: false,
    missing_keywords: ["量子引力"],
  },
  { type: "eval_done", report: buildMockReport(), filename: "report_20260814_999999.json" },
];

export const MOCK_KB_BUILD_EVENTS: KbBuildEvent[] = [
  { type: "kb_build_start", total_files: 3 },
  { type: "kb_build_file", current: 1, total: 3, filename: "平台合作规则.md", chunks: 4 },
  { type: "kb_build_file", current: 2, total: 3, filename: "食品安全手册.md", chunks: 4 },
  { type: "kb_build_file", current: 3, total: 3, filename: "门店运营手册.md", chunks: 4 },
  { type: "kb_build_done", total_docs: 3, total_chunks: 12, collection_count: 12 },
];
