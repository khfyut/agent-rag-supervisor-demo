import { MetricCard } from "../../components";
import { formatPct } from "../../api/client";
import type { EvalReportMeta } from "../../types";

export function MetricGrid({ meta }: { meta: EvalReportMeta }) {
  const rate = (v: number) => formatPct(v);
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4" data-testid="metric-grid">
      <MetricCard title="任务成功率" value={rate(meta.task_success_rate)} hint={`${meta.total_cases} 个用例`} tone="good" />
      <MetricCard title="审查打回率" value={rate(meta.reviewer_pass_rate)} hint="Reviewer 通过率" tone="default" />
      <MetricCard title="平均迭代轮数" value={meta.avg_iterations} hint="Supervisor 决策轮次" tone="default" />
      <MetricCard title="平均耗时" value={`${meta.avg_elapsed_s ?? 0}s`} hint="单用例耗时" tone="default" />
      <MetricCard title="降级触发率" value={rate(meta.degradation_rate)} hint="轮次耗尽触发紧急综合" tone={meta.degradation_rate > 0.2 ? "warn" : "default"} />
      <MetricCard title="降级交付率" value={rate(meta.degradation_delivery_rate)} hint="partial / 降级用例" tone="default" />
      <MetricCard title="诚实失败率" value={rate(meta.honest_failure_rate)} hint="failed 不硬编" tone={meta.honest_failure_rate > 0 ? "bad" : "default"} />
      <MetricCard title="门控拦截编造引用" value={meta.hallucination_blocked} hint="Guardrail 拦截次数" tone={meta.hallucination_blocked > 0 ? "bad" : "default"} />
    </div>
  );
}
