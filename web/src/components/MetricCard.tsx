// 指标卡：评估看板等页面复用。

export interface MetricCardProps {
  title: string;
  value: string | number;
  hint?: string;
  tone?: "default" | "good" | "warn" | "bad";
}

const TONE_CLS: Record<NonNullable<MetricCardProps["tone"]>, string> = {
  default: "border-slate-200 bg-white",
  good: "border-emerald-200 bg-emerald-50",
  warn: "border-amber-200 bg-amber-50",
  bad: "border-rose-200 bg-rose-50",
};

export function MetricCard({ title, value, hint, tone = "default" }: MetricCardProps) {
  return (
    <div
      className={`rounded-xl border p-4 shadow-sm ${TONE_CLS[tone]}`}
      data-testid="metric-card"
    >
      <div className="text-sm text-slate-500">{title}</div>
      <div className="mt-1 text-2xl font-bold text-slate-900">{value}</div>
      {hint ? <div className="mt-1 text-xs text-slate-400">{hint}</div> : null}
    </div>
  );
}
