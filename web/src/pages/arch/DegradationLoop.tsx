const STATES = [
  {
    key: "verified",
    title: "verified 正常交付",
    color: "border-emerald-300 bg-emerald-50",
    text: "Supervisor 汇总草稿 → Reviewer 质检出 pass → 带引用交付最终报告",
  },
  {
    key: "partial",
    title: "partial 阶段快报",
    color: "border-amber-300 bg-amber-50",
    text: "轮次耗尽 → emergency_synthesizer 产出带置信度的三区块报告 → guardrail 规则校验通过，附免责声明交付",
  },
  {
    key: "failed",
    title: "failed 诚实降级",
    color: "border-rose-300 bg-rose-50",
    text: "guardrail 校验失败（结构缺失 / 引用疑似编造 / confidence 非法）→ 如实告知原因与已有信息，绝不硬编答案",
  },
];

export function DegradationLoop() {
  return (
    <div className="grid gap-3 md:grid-cols-3" data-testid="degradation-loop">
      {STATES.map((s, i) => (
        <div key={s.key} className={`rounded-xl border p-4 ${s.color}`}>
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white text-xs font-bold text-slate-700">
              {i + 1}
            </span>
            <div className="text-sm font-semibold text-slate-900">{s.title}</div>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-slate-700">{s.text}</p>
        </div>
      ))}
    </div>
  );
}
