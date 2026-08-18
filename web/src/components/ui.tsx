// 通用展示组件：状态点 / 区块 / 进度条 / 引用徽标 / 加载 / 空态 / 错误提示。

import type { ReactNode } from "react";

// ---------- 状态小圆点 ----------
export function StatusPill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${
        ok
          ? "border-emerald-300 bg-emerald-50 text-emerald-700"
          : "border-rose-300 bg-rose-50 text-rose-700"
      }`}
      data-testid="status-pill"
    >
      <span className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-emerald-500" : "bg-rose-500"}`} />
      {label}
    </span>
  );
}

// ---------- 区块容器 ----------
export function Section({
  title,
  desc,
  actions,
  children,
}: {
  title: string;
  desc?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="section">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          {desc ? <p className="mt-0.5 text-sm text-slate-500">{desc}</p> : null}
        </div>
        {actions ? <div className="shrink-0">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

// ---------- 进度条（知识库重建等） ----------
export function ProgressBar({
  current,
  total,
  label,
  detail,
}: {
  current: number;
  total: number;
  label?: string;
  detail?: string;
}) {
  const pct = total > 0 ? Math.round((current / total) * 100) : 0;
  return (
    <div data-testid="progress-bar">
      <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
        <span>{label ?? `进度 ${current}/${total}`}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full rounded-full bg-indigo-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      {detail ? <div className="mt-1 text-xs text-slate-400">{detail}</div> : null}
    </div>
  );
}

// ---------- 引用核验徽标 ----------
export function CitationBadge({ valid }: { valid: boolean }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
        valid ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"
      }`}
      data-testid="citation-badge"
    >
      {valid ? "✓ 引用有效" : "✗ 引用缺失"}
    </span>
  );
}

// ---------- 加载 / 空态 ----------
export function Loading({ text = "加载中…" }: { text?: string }) {
  return <div className="py-6 text-center text-sm text-slate-400">{text}</div>;
}

export function Empty({ text = "暂无数据" }: { text?: string }) {
  return <div className="py-6 text-center text-sm text-slate-400">{text}</div>;
}

// ---------- 错误提示 ----------
export function ErrorNotice({ message }: { message: string }) {
  return (
    <div
      className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
      role="alert"
      data-testid="error-notice"
    >
      出错了：{message}
    </div>
  );
}
