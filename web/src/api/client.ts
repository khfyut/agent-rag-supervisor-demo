// 类型化 API 封装：全部以 CONTRACT.md 第 2 节接口清单为准。
// 导出签名与页面层 local/localApi.ts 对齐（streamAsk / fetchKbDocs / streamEvalRun 等），方便整合替换。

import { postSse } from "./sse";
import type {
  EvalEvent,
  EvalReport,
  EvalReportMeta,
  KbBuildEvent,
  KbDoc,
  KbSearchResult,
  MonitorRun,
  MonitorRunMeta,
  SystemStatus,
  WorkerSpec,
} from "../types";

// ---------- 问答 ----------
export interface AskBody {
  question: string;
  provider?: string | null;
  max_iterations?: number | null;
}

export function streamAsk(
  body: AskBody,
  onEvent: (eventName: string, data: unknown) => void,
): AbortController {
  return postSse("/api/ask", body, onEvent);
}

// ---------- 知识库 ----------
export interface KbDocsResponse {
  docs: KbDoc[];
  dirty: boolean;
}

async function getJson<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const payload = (await resp.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      /* 忽略 */
    }
    throw new Error(detail);
  }
  return (await resp.json()) as T;
}

async function postJson<T>(url: string, body: Record<string, unknown>): Promise<T> {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const payload = (await resp.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      /* 忽略 */
    }
    throw new Error(detail);
  }
  return (await resp.json()) as T;
}

async function sendForm(url: string, form: FormData, method = "POST"): Promise<unknown> {
  const resp = await fetch(url, { method, body: form });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const payload = (await resp.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      /* 忽略 */
    }
    throw new Error(detail);
  }
  return (await resp.json()) as unknown;
}

export function fetchKbDocs(): Promise<KbDocsResponse> {
  return getJson<KbDocsResponse>("/api/kb/docs");
}

export interface KbDocContent {
  name: string;
  content: string;
}

export function fetchKbDoc(name: string): Promise<KbDocContent> {
  return getJson<KbDocContent>(`/api/kb/docs/${encodeURIComponent(name)}`);
}

export function uploadKbDoc(file: File): Promise<KbDocsResponse> {
  const form = new FormData();
  form.append("file", file);
  return sendForm("/api/kb/docs", form).then((data) => data as KbDocsResponse);
}

export function deleteKbDoc(name: string): Promise<KbDocsResponse> {
  return fetch(`/api/kb/docs/${encodeURIComponent(name)}`, { method: "DELETE" }).then(
    async (resp) => {
      if (!resp.ok) {
        let detail = `HTTP ${resp.status}`;
        try {
          const payload = (await resp.json()) as { detail?: string };
          if (payload.detail) detail = payload.detail;
        } catch {
          /* 忽略 */
        }
        throw new Error(detail);
      }
      return (await resp.json()) as KbDocsResponse;
    },
  );
}

export function streamKbRebuild(
  onEvent: (event: KbBuildEvent) => void,
): AbortController {
  return postSse("/api/kb/rebuild", {}, (name, data) =>
    onEvent({ type: name, ...(data as object) } as KbBuildEvent),
  );
}

export function searchKb(
  query: string,
  k: number,
): Promise<{ results: KbSearchResult[] }> {
  return postJson<{ results: KbSearchResult[] }>("/api/kb/search", { query, k });
}

// ---------- 评估 ----------
export function fetchEvalReports(): Promise<{ reports: EvalReportMeta[] }> {
  return getJson<{ reports: EvalReportMeta[] }>("/api/eval/reports");
}

export function fetchEvalReport(filename: string): Promise<EvalReport> {
  return getJson<EvalReport>(`/api/eval/reports/${encodeURIComponent(filename)}`);
}

export interface EvalRunBody {
  provider?: string | null;
  limit?: number | null;
  max_iterations?: number | null;
}

export function streamEvalRun(
  body: EvalRunBody,
  onEvent: (event: EvalEvent) => void,
): AbortController {
  return postSse("/api/eval/run", body, (name, data) =>
    onEvent({ type: name, ...(data as object) } as EvalEvent),
  );
}

// ---------- 运行监测 ----------
export function fetchMonitorRuns(): Promise<{ runs: MonitorRunMeta[] }> {
  return getJson<{ runs: MonitorRunMeta[] }>("/api/monitor/runs");
}

export function fetchMonitorRun(runId: string): Promise<{ run: MonitorRun }> {
  return getJson<{ run: MonitorRun }>(`/api/monitor/runs/${encodeURIComponent(runId)}`);
}

// ---------- 状态 / 角色池 ----------
export function fetchStatus(): Promise<SystemStatus> {
  return getJson<SystemStatus>("/api/status");
}

export function fetchWorkers(): Promise<WorkerSpec[]> {
  return getJson<WorkerSpec[]>("/api/workers");
}

// ---------- 格式化小工具 ----------
export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function formatPct(value: number | undefined | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}
