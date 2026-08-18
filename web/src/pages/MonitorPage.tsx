// 数据监测页：查看一次问答调用中所有 Agent 的完整思考过程——
// 主管每一轮的决策、专家每次工具调用的参数与返回、质检判定、门控结果。

import { useEffect, useState } from "react";
import { fetchMonitorRun, fetchMonitorRuns } from "../api/client";
import { Empty, ErrorNotice, Layout, Loading, MarkdownAnswer, QualityBadge } from "../components";
import type { MonitorMessage, MonitorRun, MonitorRunMeta, MonitorStep } from "../types";

const NODE_STYLES: Record<string, { dot: string; badge: string; label: string }> = {
  supervisor: { dot: "bg-indigo-500", badge: "bg-indigo-50 text-indigo-700", label: "主管决策" },
  worker: { dot: "bg-sky-500", badge: "bg-sky-50 text-sky-700", label: "专家执行" },
  reviewer: { dot: "bg-violet-500", badge: "bg-violet-50 text-violet-700", label: "质检" },
  emergency_synthesizer: { dot: "bg-amber-500", badge: "bg-amber-50 text-amber-700", label: "紧急综合" },
  guardrail: { dot: "bg-emerald-500", badge: "bg-emerald-50 text-emerald-700", label: "规则门控" },
};

const ROLE_BADGE: Record<string, string> = {
  ai: "bg-indigo-50 text-indigo-700",
  tool: "bg-emerald-50 text-emerald-700",
  human: "bg-amber-50 text-amber-700",
  system: "bg-slate-100 text-slate-600",
};

function statusBadge(run: MonitorRunMeta) {
  if (run.status === "running") {
    return <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">运行中</span>;
  }
  if (run.status === "error") {
    return <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-700">出错</span>;
  }
  return <QualityBadge quality={run.quality} />;
}

function ToolCallView({ call }: { call: { name: string; args: Record<string, unknown>; result?: string | null } }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3" data-testid="monitor-tool-call">
      <p className="text-xs font-semibold text-slate-700">{call.name}</p>
      <div className="mt-1.5 space-y-1.5">
        <div>
          <p className="text-[11px] text-slate-400">参数</p>
          <pre className="max-h-28 overflow-auto rounded bg-slate-900 p-2 text-[11px] leading-relaxed text-slate-100">
            {JSON.stringify(call.args ?? {}, null, 2)}
          </pre>
        </div>
        {call.result !== undefined && call.result !== null ? (
          <div>
            <p className="text-[11px] text-slate-400">返回结果</p>
            <pre className="max-h-40 overflow-auto rounded bg-slate-900 p-2 text-[11px] leading-relaxed text-emerald-200">
              {call.result}
            </pre>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <details className="mt-2 rounded-lg border border-slate-200 bg-slate-50" data-testid="monitor-json-block">
      <summary className="cursor-pointer px-3 py-1.5 text-xs font-medium text-slate-500">{label}</summary>
      <pre className="max-h-60 overflow-auto border-t border-slate-200 p-2 text-[11px] leading-relaxed text-slate-700">
        {JSON.stringify(value ?? null, null, 2)}
      </pre>
    </details>
  );
}

function ThoughtLog({ log }: { log: MonitorMessage[] }) {
  return (
    <details className="mt-2 rounded-lg border border-slate-200 bg-slate-50" data-testid="monitor-thought-log">
      <summary className="cursor-pointer px-3 py-1.5 text-xs font-medium text-slate-500">
        思考过程（{log.length} 条消息）
      </summary>
      <div className="space-y-2 border-t border-slate-200 p-3">
        {log.map((msg, i) => (
          <div key={i} className="rounded border border-slate-100 bg-white p-2">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${ROLE_BADGE[msg.role] ?? "bg-slate-100 text-slate-600"}`}
              >
                {msg.role}
              </span>
              {msg.name ? <span className="font-mono text-[10px] text-slate-400">{msg.name}</span> : null}
              {msg.tool_call_id ? (
                <span className="font-mono text-[10px] text-slate-400">id:{msg.tool_call_id.slice(0, 8)}</span>
              ) : null}
            </div>
            {msg.content ? (
              <p className="mt-1 whitespace-pre-wrap text-[11px] leading-relaxed text-slate-700">{msg.content}</p>
            ) : null}
            {msg.tool_calls?.map((tc, j) => (
              <pre key={j} className="mt-1 max-h-32 overflow-auto rounded bg-slate-900 p-2 text-[10px] leading-relaxed text-slate-100">
                {tc.name} {JSON.stringify(tc.args, null, 2)}
              </pre>
            ))}
          </div>
        ))}
      </div>
    </details>
  );
}

function StepCard({ step }: { step: MonitorStep }) {
  const style = NODE_STYLES[step.node] ?? NODE_STYLES.supervisor;
  const title =
    step.node === "supervisor"
      ? `第 ${(step.iteration ?? 0) + 1} 轮 → ${step.next ?? ""}`
      : step.node === "worker"
        ? `${step.worker ?? ""}`
        : step.node === "reviewer"
          ? `判定：${step.verdict === "pass" ? "通过" : "打回"}`
          : step.node === "emergency_synthesizer"
            ? `置信度 ${((step.confidence ?? 0) * 100).toFixed(0)}%`
            : step.node === "guardrail"
              ? step.passed
                ? "通过（放行）"
                : "拦截"
              : "";

  return (
    <div className="relative pl-6" data-testid="monitor-step">
      <span className={`absolute left-1 top-1.5 h-2.5 w-2.5 rounded-full ${style.dot}`} />
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${style.badge}`}>
            {style.label}
          </span>
          <span className="text-sm font-semibold text-slate-800">{title}</span>
          {step.node === "guardrail" && !step.passed ? (
            <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs text-rose-700">{step.quality}</span>
          ) : null}
        </div>

        {step.instructions ? (
          <p className="mt-2 text-xs leading-relaxed text-slate-600">
            <span className="font-medium text-slate-400">指令：</span>
            {step.instructions}
          </p>
        ) : null}

        {step.input !== undefined ? <JsonBlock label="输入" value={step.input} /> : null}

        {step.tool_calls && step.tool_calls.length > 0 ? (
          <div className="mt-3 space-y-2">
            <p className="text-xs font-medium text-slate-500">工具调用（{step.tool_calls.length} 次）</p>
            {step.tool_calls.map((call, i) => (
              <ToolCallView key={i} call={call} />
            ))}
          </div>
        ) : null}

        {step.findings && step.findings.length > 0 ? (
          <div className="mt-3 space-y-1.5">
            <p className="text-xs font-medium text-slate-500">产出发现</p>
            {step.findings.map((f, i) => (
              <div key={i} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                {f.summary}
                {f.source || f.chunk_id ? (
                  <span className="mt-0.5 block font-mono text-[11px] text-slate-400">
                    {f.source ?? "—"} / {f.chunk_id ?? "无引用"}
                  </span>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}

        {step.self_check ? (
          <p className="mt-2 text-[11px] text-slate-400">自检：{step.self_check}</p>
        ) : null}
        {step.error ? (
          <p className="mt-2 rounded bg-rose-50 px-2 py-1 text-[11px] text-rose-600">错误：{step.error}</p>
        ) : null}

        {step.log && step.log.length > 0 ? <ThoughtLog log={step.log} /> : null}
        {step.output !== undefined ? <JsonBlock label="输出" value={step.output} /> : null}

        {step.feedback ? (
          <p className="mt-2 rounded bg-violet-50 px-3 py-2 text-xs text-violet-700">
            <span className="font-medium">反馈：</span>
            {step.feedback}
          </p>
        ) : null}

        {step.report ? (
          <div className="mt-3 space-y-2 text-xs text-slate-700">
            <p className="rounded bg-amber-50 px-3 py-2">
              <span className="font-medium text-amber-700">摘要：</span>
              {step.report.summary}
            </p>
            {step.report.confirmed_facts.length > 0 ? (
              <div>
                <p className="text-[11px] font-medium text-slate-400">已确认事实</p>
                {step.report.confirmed_facts.map((fact, i) => (
                  <p key={i} className="mt-1">
                    · {fact.statement}
                    {fact.chunk_id ? <span className="font-mono text-[11px] text-slate-400">（{fact.chunk_id}）</span> : null}
                  </p>
                ))}
              </div>
            ) : null}
            {step.report.insights.length > 0 ? (
              <div>
                <p className="text-[11px] font-medium text-slate-400">初步洞察</p>
                {step.report.insights.map((item, i) => (
                  <p key={i} className="mt-1">· {item}</p>
                ))}
              </div>
            ) : null}
            {step.report.to_verify.length > 0 ? (
              <div>
                <p className="text-[11px] font-medium text-slate-400">需后续核实</p>
                {step.report.to_verify.map((item, i) => (
                  <p key={i} className="mt-1">· {item}</p>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {step.node === "guardrail" && step.reason ? (
          <p className="mt-2 text-[11px] text-slate-500">原因：{step.reason}</p>
        ) : null}
      </div>
    </div>
  );
}

export default function MonitorPage() {
  const [runs, setRuns] = useState<MonitorRunMeta[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<MonitorRun | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadRuns = () => {
    fetchMonitorRuns()
      .then((res) => {
        setRuns(res.runs);
        setLoadError(null);
      })
      .catch((err) => setLoadError(err instanceof Error ? err.message : String(err)));
  };

  useEffect(() => {
    loadRuns();
    const timer = window.setInterval(() => {
      loadRuns();
    }, 5000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    fetchMonitorRun(selectedId)
      .then((res) => {
        setDetail(res.run);
        setDetailLoading(false);
      })
      .catch((err) => {
        setDetailLoading(false);
        setLoadError(err instanceof Error ? err.message : String(err));
      });
  }, [selectedId]);

  const running = runs?.some((r) => r.status === "running") ?? false;

  return (
    <Layout>
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">数据监测</h1>
            <p className="mt-1 text-sm text-slate-500">
              单次调用的完整 Agent 思考过程：主管决策、工具调用参数与返回、质检与门控
            </p>
          </div>
          <span className="text-xs text-slate-400">{running ? "有任务运行中，自动刷新…" : "每 5 秒自动刷新"}</span>
        </div>

        {loadError ? <ErrorNotice message={loadError} /> : null}

        <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-slate-900">运行记录</h2>
            {!runs ? (
              <Loading />
            ) : runs.length === 0 ? (
              <Empty text="暂无运行记录，先去问答页跑一次" />
            ) : (
              <ul className="space-y-2">
                {runs.map((run) => (
                  <li key={run.run_id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(run.run_id)}
                      className={`w-full rounded-xl border p-3 text-left transition ${
                        selectedId === run.run_id
                          ? "border-indigo-300 bg-indigo-50"
                          : "border-slate-200 bg-white hover:border-indigo-200 hover:bg-slate-50"
                      }`}
                      data-testid="monitor-run-item"
                    >
                      <p className="truncate text-xs text-slate-800">{run.question}</p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        {statusBadge(run)}
                        <span className="font-mono text-[11px] text-slate-400">{run.run_id}</span>
                        <span className="text-[11px] text-slate-400">{run.iterations} 轮</span>
                      </div>
                      <p className="mt-1 text-[11px] text-slate-400">{run.created_at}</p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-2xl border border-slate-200 bg-slate-50 p-5 shadow-sm">
            {detailLoading ? (
              <Loading text="轨迹加载中…" />
            ) : detail ? (
              <div className="space-y-4">
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-base font-semibold text-slate-900">{detail.question}</h2>
                    {statusBadge(detail)}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-400">
                    <span className="font-mono">run_id: {detail.run_id}</span>
                    <span>provider: {detail.provider || "默认"}</span>
                    <span>创建: {detail.created_at}</span>
                    <span>迭代: {detail.iterations} 轮</span>
                    {detail.finish_reason ? <span>结束: {detail.finish_reason}</span> : null}
                  </div>
                  {detail.error ? (
                    <p className="mt-2 rounded bg-rose-50 px-3 py-2 text-xs text-rose-700">{detail.error}</p>
                  ) : null}
                </div>

                <div className="space-y-3">
                  <p className="text-sm font-semibold text-slate-700">执行轨迹（{detail.steps.length} 步）</p>
                  {detail.steps.length === 0 ? (
                    <Empty text="该运行没有留下步骤记录" />
                  ) : (
                    detail.steps.map((step, i) => <StepCard key={i} step={step} />)
                  )}
                </div>

                {detail.final_answer ? (
                  <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                    <h3 className="mb-2 text-sm font-semibold text-slate-700">最终交付</h3>
                    <MarkdownAnswer content={detail.final_answer} />
                  </div>
                ) : null}
              </div>
            ) : (
              <Empty text="选择左侧一条运行记录，查看它的完整思考过程" />
            )}
          </section>
        </div>
      </div>
    </Layout>
  );
}
