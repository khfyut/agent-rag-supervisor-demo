import { useState } from "react";
import { streamKbRebuild } from "../../api/client";
import { ErrorNotice, ProgressBar } from "../../components";
import type { KbBuildEvent } from "../../types";

export interface RebuildPanelProps {
  dirty: boolean;
  onDone: () => void;
}

export function RebuildPanel({ dirty, onDone }: RebuildPanelProps) {
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<KbBuildEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  const startEvent = events.find((e) => e.type === "kb_build_start");
  const fileEvents = events.filter((e) => e.type === "kb_build_file");
  const doneEvent = events.find((e) => e.type === "kb_build_done");
  const totalFiles = startEvent?.type === "kb_build_start" ? startEvent.total_files : 0;
  const lastFile = fileEvents[fileEvents.length - 1];

  const rebuild = () => {
    setError(null);
    setEvents([]);
    setRunning(true);
    streamKbRebuild((ev) => {
      setEvents((prev) => [...prev, ev]);
      if (ev.type === "kb_build_done") {
        setRunning(false);
        onDone();
      } else if (ev.type === "kb_build_error") {
        setRunning(false);
        setError(ev.message);
      }
    });
  };

  return (
    <div className="space-y-3" data-testid="rebuild-panel">
      {dirty ? (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-2.5 text-sm text-amber-800" data-testid="dirty-banner">
          ⚠ 知识库有变更，重建向量库后才会生效
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <button
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          onClick={rebuild}
          disabled={running}
          data-testid="rebuild-button"
        >
          {running ? "重建中…" : dirty ? "重建向量库" : "重新构建向量库"}
        </button>
        {doneEvent && doneEvent.type === "kb_build_done" ? (
          <span className="text-sm text-emerald-700" data-testid="rebuild-done">
            重建完成：{doneEvent.total_docs} 个文档 / {doneEvent.total_chunks} 个分片（collection {doneEvent.collection_count}）
          </span>
        ) : null}
      </div>

      {error ? <ErrorNotice message={error} /> : null}

      {running || fileEvents.length > 0 ? (
        <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4">
          <ProgressBar
            current={lastFile?.current ?? 0}
            total={totalFiles || 1}
            label="逐文件重建进度"
            detail={
              lastFile
                ? `${lastFile.filename}：产出 ${lastFile.chunks} 个分片`
                : "准备中…"
            }
          />
          <div className="max-h-32 space-y-1 overflow-y-auto text-xs text-slate-500">
            {fileEvents.map((e) => (
              <div key={e.filename}>
                [{e.current}/{e.total}] {e.filename} → {e.chunks} 分片
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
