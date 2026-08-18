import { Fragment, useState } from "react";
import { CitationBadge, Empty, QualityBadge } from "../../components";
import type { EvalCaseResult } from "../../types";

export function CaseTable({ cases }: { cases: EvalCaseResult[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  if (!cases.length) return <Empty text="该报告没有用例数据" />;

  return (
    <div className="overflow-x-auto" data-testid="case-table">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs text-slate-500">
            <th className="py-2 pr-3">用例</th>
            <th className="py-2 pr-3">难度</th>
            <th className="py-2 pr-3">结果</th>
            <th className="py-2 pr-3">缺失关键词</th>
            <th className="py-2 pr-3">迭代</th>
            <th className="py-2 pr-3">引用</th>
            <th className="py-2 pr-3">Reviewer</th>
            <th className="py-2 pr-3">质量</th>
            <th className="py-2 pr-3">结束原因</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => {
            const open = expanded === c.id;
            const missing = c.missing_keywords ?? [];
            const citations = Array.isArray(c.citations) ? c.citations : null;
            const verdicts = c.reviewer_verdicts ?? [];
            const hits = c.keywords_hit ?? [];
            return (
              <Fragment key={c.id}>
                <tr
                  className="cursor-pointer border-b border-slate-100 hover:bg-slate-50"
                  onClick={() => setExpanded(open ? null : c.id)}
                  data-testid="case-row"
                >
                  <td className="py-2 pr-3 font-medium text-slate-800">{c.id}</td>
                  <td className="py-2 pr-3 text-slate-600">{c.level}</td>
                  <td className="py-2 pr-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                        c.success ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"
                      }`}
                    >
                      {c.success ? "PASS" : "FAIL"}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-slate-600">
                    {missing.length ? missing.join("、") : "—"}
                  </td>
                  <td className="py-2 pr-3 text-slate-600">{c.iterations}</td>
                  <td className="py-2 pr-3">
                    {citations ? (
                      <>
                        <CitationBadge valid={Boolean(c.citation_valid)} />
                        {citations.length ? (
                          <span className="ml-1 text-xs text-slate-400">×{citations.length}</span>
                        ) : null}
                      </>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="py-2 pr-3 text-slate-600">
                    {verdicts.length ? verdicts.join(" → ") : "—"}
                  </td>
                  <td className="py-2 pr-3">
                    <QualityBadge quality={c.quality} />
                  </td>
                  <td className="py-2 pr-3 text-slate-600">{c.finish_reason || "—"}</td>
                  <td className="py-2 text-slate-400">{open ? "▲" : "▼"}</td>
                </tr>
                {open ? (
                  <tr className="border-b border-slate-100 bg-slate-50">
                    <td colSpan={10} className="px-4 py-3">
                      <div className="grid gap-3 text-sm md:grid-cols-2">
                        <div>
                          <div className="mb-1 text-xs font-semibold text-slate-500">最终回答</div>
                          <div className="whitespace-pre-wrap rounded-lg bg-white p-3 text-slate-700">
                            {c.final_answer || "（空）"}
                          </div>
                        </div>
                        <div>
                          <div className="mb-1 text-xs font-semibold text-slate-500">引用明细 / Guardrail</div>
                          <div className="rounded-lg bg-white p-3 text-slate-700">
                            <div>引用：{citations && citations.length ? citations.join("、") : "无"}</div>
                            <div className="mt-1">Guardrail：{c.guardrail_reason || "未触发"}</div>
                            <div className="mt-1">命中关键词：{hits.length ? hits.join("、") : "无"}</div>
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
