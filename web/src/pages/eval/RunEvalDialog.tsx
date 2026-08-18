import { useEffect, useState } from "react";
import { streamEvalRun } from "../../api/client";
import { ErrorNotice, ProgressBar } from "../../components";
import type { EvalEvent } from "../../types";

export interface RunEvalDialogProps {
  open: boolean;
  onClose: () => void;
  onFinished: (filename: string) => void;
}

export function RunEvalDialog({ open, onClose, onFinished }: RunEvalDialogProps) {
  const [provider, setProvider] = useState("");
  const [limit, setLimit] = useState("");
  const [maxIterations, setMaxIterations] = useState("");
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<EvalEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setEvents([]);
      setError(null);
      setRunning(false);
    }
  }, [open]);

  if (!open) return null;

  const started = events.find((e) => e.type === "eval_start");
  const doneCases = events.filter((e) => e.type === "eval_case").length;
  const total = started?.type === "eval_start" ? started.total : 0;
  const doneEvent = events.find((e) => e.type === "eval_done");
  const errorEvent = events.find((e) => e.type === "eval_error");

  const submit = () => {
    setError(null);
    setEvents([]);
    setRunning(true);
    streamEvalRun(
      {
        provider: provider || null,
        limit: limit ? Number(limit) : null,
        max_iterations: maxIterations ? Number(maxIterations) : null,
      },
      (ev) => {
        setEvents((prev) => [...prev, ev]);
        if (ev.type === "eval_done") {
          setRunning(false);
          onFinished(ev.filename);
        } else if (ev.type === "eval_error") {
          setRunning(false);
          setError(ev.message);
        }
      },
    );
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/40 p-4" role="dialog" data-testid="run-eval-dialog">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-900">运行评估</h3>
          <button
            className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-100"
            onClick={onClose}
            disabled={running}
            aria-label="关闭"
          >
            ✕
          </button>
        </div>

        <div className="grid gap-3">
          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Provider（留空走 .env）</span>
            <select
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              data-testid="eval-provider"
            >
              <option value="">默认（.env）</option>
              <option value="mock">mock（无 key 演示）</option>
              <option value="openai">openai</option>
              <option value="ollama">ollama</option>
              <option value="deepseek">deepseek</option>
              <option value="minimax">minimax</option>
            </select>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="mb-1 block text-slate-600">Limit（留空跑全部）</span>
              <input
                type="number"
                min={1}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                data-testid="eval-limit"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-slate-600">Max Iterations（留空用配置）</span>
              <input
                type="number"
                min={0}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                value={maxIterations}
                onChange={(e) => setMaxIterations(e.target.value)}
                data-testid="eval-max-iterations"
              />
            </label>
          </div>
        </div>

        {error ? <div className="mt-4"><ErrorNotice message={error} /></div> : null}

        {events.length > 0 ? (
          <div className="mt-4 space-y-2" data-testid="eval-progress">
            <ProgressBar
              current={doneCases}
              total={total || 1}
              label={running ? "评估进行中" : doneEvent ? "评估完成" : "准备中"}
              detail={
                total
                  ? `已完成 ${doneCases}/${total} 个用例`
                  : undefined
              }
            />
            <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
              {events
                .filter((e) => e.type === "eval_case")
                .map((e) =>
                  e.type === "eval_case" ? (
                    <div key={`${e.id}-${e.index}`}>
                      [{e.id}]（{e.level}）{e.success ? "PASS" : "FAIL"}
                      {e.missing_keywords.length ? ` 缺失: ${e.missing_keywords.join("、")}` : ""}
                    </div>
                  ) : null,
                )}
            </div>
            {doneEvent && doneEvent.type === "eval_done" ? (
              <div className="rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                报告已生成：{doneEvent.filename}
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="mt-5 flex justify-end gap-2">
          <button
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
            onClick={onClose}
            disabled={running}
          >
            取消
          </button>
          <button
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            onClick={submit}
            disabled={running}
            data-testid="eval-run-submit"
          >
            {running ? "运行中…" : "开始评估"}
          </button>
        </div>
      </div>
    </div>
  );
}
