// 全局布局：顶部导航 + 系统状态条（轮询 /api/status）+ 页脚。
// 同时导出 NavBar / StatusBar 供页面按需使用。

import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { fetchStatus } from "../api/client";
import type { SystemStatus } from "../types";
import { StatusPill } from "./ui";

const NAV_ITEMS = [
  { to: "/ask", label: "问答演示" },
  { to: "/eval", label: "评估看板" },
  { to: "/kb", label: "知识库管理" },
  { to: "/arch", label: "架构讲解" },
  { to: "/monitor", label: "数据监测" },
];

export function NavBar() {
  return (
    <nav className="flex items-center gap-1" data-testid="main-nav">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            `rounded-lg px-3 py-1.5 text-sm font-medium transition ${
              isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100"
            }`
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

export function StatusBar() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [statusError, setStatusError] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetchStatus()
        .then((s) => {
          if (alive) {
            setStatus(s);
            setStatusError(false);
          }
        })
        .catch(() => {
          if (alive) setStatusError(true);
        });
    load();
    const timer = window.setInterval(load, 15_000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="flex items-center gap-2 text-xs" data-testid="status-bar">
      {statusError ? (
        <StatusPill ok={false} label="API 不可达" />
      ) : status ? (
        <>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-slate-600">
            {status.provider} / {status.model}
          </span>
          <StatusPill ok={status.kb_ready} label={status.kb_ready ? "KB 就绪" : "KB 未就绪"} />
          <StatusPill ok={status.db_ready} label={status.db_ready ? "DB 就绪" : "DB 未就绪"} />
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-slate-600">
            报告 {status.reports_count} 份
          </span>
        </>
      ) : (
        <span className="text-slate-400">状态加载中…</span>
      )}
    </div>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-100">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-6">
            <div className="text-base font-bold text-slate-900">Multi-Agent RAG Supervisor</div>
            <NavBar />
          </div>
          <StatusBar />
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
      <footer className="mx-auto max-w-6xl px-4 pb-8 text-center text-xs text-slate-400">
        演示展示型前端 · Supervisor 模式 + 角色池 + Reviewer 质检 + Guardrail 降级闭环
      </footer>
    </div>
  );
}
