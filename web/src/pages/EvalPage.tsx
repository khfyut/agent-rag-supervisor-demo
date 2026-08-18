import { useCallback, useEffect, useState } from "react";
import { fetchEvalReport, fetchEvalReports, formatPct } from "../api/client";
import { Empty, ErrorNotice, Layout, Loading, QualityBadge, Section } from "../components";
import type { EvalReport, EvalReportMeta } from "../types";
import { CaseTable } from "./eval/CaseTable";
import { MetricGrid } from "./eval/MetricGrid";
import { RunEvalDialog } from "./eval/RunEvalDialog";

export default function EvalPage() {
  const [reports, setReports] = useState<EvalReportMeta[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<EvalReportMeta | null>(null);
  const [detail, setDetail] = useState<EvalReport | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const loadReports = useCallback(async () => {
    try {
      const resp = await fetchEvalReports();
      setReports(resp.reports);
      setLoadError(null);
      if (resp.reports.length && !selected) {
        setSelected(resp.reports[0]);
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
    }
  }, [selected]);

  useEffect(() => {
    void loadReports();
  }, [loadReports]);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    setDetail(null);
    fetchEvalReport(selected.filename)
      .then((report) => {
        setDetail(report);
        setDetailLoading(false);
      })
      .catch((err) => {
        setDetailLoading(false);
        setNotice(err instanceof Error ? err.message : String(err));
      });
  }, [selected]);

  const handleFinished = (filename: string) => {
    setDialogOpen(false);
    setNotice(`评估完成，报告已生成：${filename}`);
    void loadReports();
  };

  const meta = selected ?? (reports && reports[0]) ?? null;

  return (
    <Layout>
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">评估看板</h1>
            <p className="mt-1 text-sm text-slate-500">
              质量与过程指标：成功率 / 审查打回 / 迭代 / 耗时 / 降级与门控
            </p>
          </div>
          <button
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            onClick={() => setDialogOpen(true)}
            data-testid="open-eval-run"
          >
            运行评估
          </button>
        </div>

        {notice ? (
          <div className="rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm text-indigo-700" data-testid="page-notice">
            {notice}
          </div>
        ) : null}

        {loadError ? <ErrorNotice message={loadError} /> : null}

        {meta ? (
          <Section
            title="指标总览"
            desc={`${meta.filename} · ${meta.generated_at} · ${meta.provider} / ${meta.model}`}
          >
            <MetricGrid meta={meta} />
          </Section>
        ) : null}

        <Section
          title="历史报告"
          desc="点击报告查看逐用例明细；点击行展开单用例详情"
        >
          {!reports ? (
            <Loading />
          ) : reports.length === 0 ? (
            <Empty text="暂无报告，点击右上角「运行评估」生成第一份" />
          ) : (
            <div className="space-y-2" data-testid="report-list">
              {reports.map((r) => (
                <button
                  key={r.filename}
                  className={`w-full rounded-xl border p-3 text-left transition ${
                    selected?.filename === r.filename
                      ? "border-indigo-300 bg-indigo-50"
                      : "border-slate-200 bg-white hover:border-indigo-200 hover:bg-slate-50"
                  }`}
                  onClick={() => setSelected(r)}
                  data-testid="report-item"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-mono text-sm text-slate-800">{r.filename}</div>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <span>{r.generated_at}</span>
                      <span>{r.provider} / {r.model}</span>
                      <span>{r.total_cases} 用例</span>
                      <span className={`font-medium ${r.task_success_rate >= 0.5 ? "text-emerald-600" : "text-rose-600"}`}>
                        成功率 {formatPct(r.task_success_rate)}
                      </span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </Section>

        <Section
          title={selected ? `逐用例明细：${selected.filename}` : "逐用例明细"}
          desc="成功 / 缺失关键词 / 引用核验 / Reviewer 判定 / 质量"
        >
          {detailLoading ? <Loading text="报告加载中…" /> : detail ? <CaseTable cases={detail.cases} /> : <Empty text="选择左侧报告查看" />}
        </Section>

        {/* 摘要行：展示所选报告质量分布 */}
        {detail ? (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
            <span className="font-medium text-slate-800">质量分布：</span>
            {["verified", "partial", "failed"].map((q) => {
              const n = detail.cases.filter((c) => (c.quality || "").toLowerCase() === q).length;
              return (
                <span key={q} className="inline-flex items-center gap-1.5">
                  <QualityBadge quality={q} /> <span>{n} 例</span>
                </span>
              );
            })}
          </div>
        ) : null}

        <RunEvalDialog
          open={dialogOpen}
          onClose={() => setDialogOpen(false)}
          onFinished={handleFinished}
        />
      </div>
    </Layout>
  );
}
