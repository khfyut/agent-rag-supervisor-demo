// 质量徽标：verified / partial / failed 三态（含未知状态兜底）。

const QUALITY_META: Record<string, { label: string; cls: string }> = {
  verified: {
    label: "verified 已验证",
    cls: "bg-emerald-100 text-emerald-800 border-emerald-300",
  },
  partial: {
    label: "partial 阶段快报",
    cls: "bg-amber-100 text-amber-800 border-amber-300",
  },
  failed: {
    label: "failed 诚实降级",
    cls: "bg-rose-100 text-rose-800 border-rose-300",
  },
  running: {
    label: "运行中",
    cls: "bg-sky-100 text-sky-800 border-sky-300",
  },
  error: {
    label: "错误",
    cls: "bg-slate-100 text-slate-600 border-slate-300",
  },
};

export function QualityBadge({ quality }: { quality: string | null | undefined }) {
  const key = (quality || "").toLowerCase();
  const meta = QUALITY_META[key] ?? {
    label: quality ? `quality=${quality}` : "未标注",
    cls: "bg-slate-100 text-slate-600 border-slate-300",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${meta.cls}`}
      data-testid="quality-badge"
    >
      {meta.label}
    </span>
  );
}
