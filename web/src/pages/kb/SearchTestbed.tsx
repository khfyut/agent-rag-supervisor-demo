import { useState } from "react";
import { searchKb } from "../../api/client";
import { CitationBadge, ErrorNotice } from "../../components";
import type { KbSearchResult } from "../../types";

export function SearchTestbed() {
  const [query, setQuery] = useState("");
  const [k, setK] = useState(4);
  const [results, setResults] = useState<KbSearchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await searchKb(query.trim(), k);
      setResults(resp.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4" data-testid="search-testbed">
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-[240px] flex-1 text-sm">
          <span className="mb-1 block text-slate-600">检索问题（测试向量检索与引用核验）</span>
          <input
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            placeholder="例如：已支付未发货的订单可以申请退款吗？"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void run();
            }}
            data-testid="search-query"
          />
        </label>
        <label className="w-56 text-sm">
          <span className="mb-1 block text-slate-600">Top-k：{k}</span>
          <input
            type="range"
            min={1}
            max={8}
            value={k}
            onChange={(e) => setK(Number(e.target.value))}
            className="w-full accent-indigo-600"
            data-testid="search-k"
          />
        </label>
        <button
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          onClick={() => void run()}
          disabled={loading || !query.trim()}
          data-testid="search-button"
        >
          {loading ? "检索中…" : "检索"}
        </button>
      </div>

      {error ? <ErrorNotice message={error} /> : null}

      {results ? (
        <div className="space-y-2" data-testid="search-results">
          {results.length === 0 ? (
            <div className="py-4 text-center text-sm text-slate-400">没有命中任何分片</div>
          ) : (
            results.map((r, i) => (
              <div key={`${r.chunk_id}-${i}`} className="rounded-xl border border-slate-200 bg-white p-4" data-testid="search-result-card">
                <div className="mb-1.5 flex flex-wrap items-center gap-2 text-xs">
                  <span className="font-mono rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">{r.chunk_id}</span>
                  <span className="text-slate-400">{r.source}</span>
                  <span className="text-slate-400">score {r.score.toFixed(4)}</span>
                  <CitationBadge valid={r.citation_valid} />
                </div>
                <p className="text-sm text-slate-700">{r.content}</p>
              </div>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
