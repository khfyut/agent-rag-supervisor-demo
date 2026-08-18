import { useEffect, useState } from "react";
import { fetchWorkers } from "../../api/client";
import { Empty, ErrorNotice, Loading } from "../../components";
import type { WorkerSpec } from "../../types";

const ROLE_LABEL: Record<string, string> = {
  rag_researcher: "📚 知识库研究员",
  sql_analyst: "📊 数据分析师",
  web_searcher: "🌐 网络研究员",
  stock_analyst: "📦 库存分析师",
};

export function WorkerPool() {
  const [workers, setWorkers] = useState<WorkerSpec[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchWorkers()
      .then(setWorkers)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  if (error) return <ErrorNotice message={error} />;
  if (!workers) return <Loading text="角色池加载中…" />;
  if (!workers.length) return <Empty text="角色池为空" />;

  return (
    <div className="grid gap-3 sm:grid-cols-2" data-testid="worker-pool">
      {workers.map((w) => (
        <div key={w.name} className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-sm font-semibold text-slate-900">
            {ROLE_LABEL[w.name] ?? w.name}
            <span className="ml-2 font-mono text-xs font-normal text-slate-400">{w.name}</span>
          </div>
          <p className="mt-1.5 text-sm text-slate-600">{w.description}</p>
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {w.tool_names.map((t) => (
              <span
                key={t}
                className="rounded-md bg-indigo-50 px-2 py-0.5 font-mono text-xs text-indigo-700"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
