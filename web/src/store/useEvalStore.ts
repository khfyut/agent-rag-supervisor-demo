// 评估报告 / 运行进度状态（页面层可自行管理状态，本 store 供需要时复用）。

import { create } from "zustand";
import { fetchEvalReport, fetchEvalReports, streamEvalRun } from "../api/client";
import type { EvalEvent, EvalReport, EvalReportMeta } from "../types";

export type EvalRunStatus = "idle" | "running" | "done" | "error";

interface EvalState {
  reports: EvalReportMeta[] | null;
  selected: EvalReportMeta | null;
  detail: EvalReport | null;
  runStatus: EvalRunStatus;
  runProgress: { total: number; cases: Array<{ id: string; level: string; success: boolean; missing_keywords: string[] }> };
  error: string | null;
  loadReports: () => Promise<void>;
  selectReport: (meta: EvalReportMeta) => Promise<void>;
  run: (body: { provider?: string | null; limit?: number | null; max_iterations?: number | null }) => void;
}

export const useEvalStore = create<EvalState>((set, get) => ({
  reports: null,
  selected: null,
  detail: null,
  runStatus: "idle",
  runProgress: { total: 0, cases: [] },
  error: null,

  loadReports: async () => {
    try {
      const resp = await fetchEvalReports();
      set({ reports: resp.reports, error: null });
      if (resp.reports.length > 0 && !get().selected) {
        const first = resp.reports[0];
        set({ selected: first });
        try {
          const detail = await fetchEvalReport(first.filename);
          set({ detail });
        } catch {
          /* 详情加载失败不阻断列表 */
        }
      }
    } catch (err) {
      set({ error: err instanceof Error ? err.message : String(err) });
    }
  },

  selectReport: async (meta) => {
    set({ selected: meta, detail: null });
    try {
      const detail = await fetchEvalReport(meta.filename);
      set({ detail });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : String(err) });
    }
  },

  run: (body) => {
    set({ runStatus: "running", runProgress: { total: 0, cases: [] }, error: null });
    streamEvalRun(body, (event: EvalEvent) => {
      if (event.type === "eval_start") {
        set({ runProgress: { total: event.total, cases: [] } });
      } else if (event.type === "eval_case") {
        set((state) => ({
          runProgress: {
            ...state.runProgress,
            cases: [
              ...state.runProgress.cases,
              {
                id: event.id,
                level: event.level,
                success: event.success,
                missing_keywords: event.missing_keywords,
              },
            ],
          },
        }));
      } else if (event.type === "eval_done") {
        set({ runStatus: "done" });
        void get().loadReports();
      } else if (event.type === "eval_error") {
        set({ runStatus: "error", error: event.message });
      }
    });
  },
}));
