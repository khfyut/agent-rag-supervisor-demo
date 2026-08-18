// 问答演示页：输入问题 → SSE 实时执行图 + 时间线 → Markdown 答案 + 引用溯源 → 本地回放。

import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { streamAsk } from "../api/client";
import {
  Layout,
  MarkdownAnswer,
  NodeGraph,
  QualityBadge,
  Timeline,
} from "../components";
import { PRESET_QUESTIONS } from "../data/presetQuestions";
import { useAskStore } from "../store/useAskStore";
import type { AskEvent } from "../types";

const PROVIDERS = [
  { value: "", label: "默认（.env）" },
  { value: "mock", label: "mock（无 key 演示）" },
  { value: "openai", label: "openai" },
  { value: "ollama", label: "ollama" },
  { value: "deepseek", label: "deepseek" },
  { value: "minimax", label: "minimax" },
];

/** 事件 → 执行图节点 */
function nodeFromEvent(event: AskEvent | undefined): string | null {
  if (!event) return null;
  switch (event.type) {
    case "run_start":
      return "supervisor";
    case "supervisor":
      return "supervisor";
    case "worker":
      return event.worker;
    case "reviewer":
      return "reviewer";
    case "emergency":
      return "emergency_synthesizer";
    case "guardrail":
      return "guardrail";
    case "done":
      return "END";
    case "error":
      return null;
  }
}

export default function AskPage() {
  const {
    status,
    events,
    error,
    runId,
    history,
    playbackIndex,
    playing,
    speed,
    startRun,
    appendEvent,
    completeRun,
    failRun,
    loadHistoryItem,
    clearHistory,
    startPlayback,
    pausePlayback,
    stepForward,
    stepBackward,
    setSpeed,
    resetPlayback,
  } = useAskStore();

  const [input, setInput] = useState("");
  const [provider, setProvider] = useState("");
  const [maxIterations, setMaxIterations] = useState("");
  const [detailNode, setDetailNode] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  // 播放定时器：按 speed 毫秒推进回放
  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      stepForward();
    }, speed);
    return () => window.clearInterval(timer);
  }, [playing, speed, stepForward]);

  // 回放到达末尾时自动暂停
  useEffect(() => {
    if (playing && playbackIndex >= events.length - 1 && events.length > 0) {
      pausePlayback();
    }
  }, [playing, playbackIndex, events.length, pausePlayback]);

  useEffect(() => {
    return () => controllerRef.current?.abort();
  }, []);

  const currentEvent = events[playbackIndex];
  const activeNode = nodeFromEvent(currentEvent);

  const doneEvent = useMemo(
    () => events.findLast((e) => e.type === "done") as Extract<AskEvent, { type: "done" }> | undefined,
    [events],
  );
  const errorEvent = useMemo(
    () => events.findLast((e) => e.type === "error") as Extract<AskEvent, { type: "error" }> | undefined,
    [events],
  );

  const run = async (questionText: string) => {
    if (!questionText.trim() || status === "running") return;
    controllerRef.current?.abort();
    startRun(questionText.trim());
    const controller = streamAsk(
      {
        question: questionText.trim(),
        provider: provider || null,
        max_iterations: maxIterations ? Number(maxIterations) : null,
      },
      (name, data) => {
        const event = { type: name, ...(data as object) } as AskEvent;
        appendEvent(event);
        if (event.type === "done") completeRun();
        if (event.type === "error") failRun(event.message);
      },
    );
    controllerRef.current = controller;
  };

  const activeFinding = doneEvent?.findings ?? [];

  return (
    <Layout>
      <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
        {/* 左列：输入 + 执行图 + 回放 */}
        <div className="space-y-5">
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">提问</h2>
            <p className="mt-0.5 text-sm text-slate-500">
              输入奶茶店运营问题，观察 Supervisor 如何调度专家并质检交付。
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {PRESET_QUESTIONS.map((q) => (
                <button
                  key={q.id}
                  type="button"
                  onClick={() => setInput(q.question)}
                  className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
                  data-testid={`preset-${q.id}`}
                >
                  {q.label}
                </button>
              ))}
            </div>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              rows={3}
              placeholder="例如：2026 年第一季度华东区门店有多少笔订单？"
              className="mt-4 w-full rounded-xl border border-slate-300 p-3 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
              data-testid="ask-input"
            />
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-slate-600">
                provider
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm outline-none focus:border-indigo-400"
                  data-testid="provider-select"
                >
                  {PROVIDERS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-600">
                max_iterations
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={maxIterations}
                  onChange={(e) => setMaxIterations(e.target.value)}
                  placeholder="默认"
                  className="w-20 rounded-lg border border-slate-300 px-2 py-1.5 text-sm outline-none focus:border-indigo-400"
                />
              </label>
              <button
                type="button"
                onClick={() => void run(input)}
                disabled={status === "running" || !input.trim()}
                className="ml-auto rounded-xl bg-indigo-600 px-5 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
                data-testid="run-button"
              >
                {status === "running" ? "运行中…" : "运行"}
              </button>
            </div>
            {provider === "mock" ? (
              <p className="mt-2 text-xs text-slate-400">
                mock 模式使用剧本化模型，无需 API key，用于演示执行流程。
              </p>
            ) : null}
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900">实时执行图</h2>
              <span className="text-xs text-slate-400">点击节点查看详情</span>
            </div>
            <NodeGraph activeNode={activeNode} onNodeClick={setDetailNode} />
            {detailNode ? (
              <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                当前节点：<span className="font-mono">{detailNode}</span>
                {activeNode === detailNode ? "（运行中/已点亮）" : ""}
              </div>
            ) : null}
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold text-slate-900">回放</h2>
              <span className="text-xs text-slate-400">
                {playbackIndex + 1}/{events.length} · 本地重放，不重跑模型
              </span>
              <div className="ml-auto flex items-center gap-2">
                <button
                  type="button"
                  onClick={resetPlayback}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                >
                  重置
                </button>
                <button
                  type="button"
                  onClick={stepBackward}
                  disabled={events.length === 0}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-40"
                >
                  上一步
                </button>
                <button
                  type="button"
                  onClick={playing ? pausePlayback : startPlayback}
                  disabled={events.length === 0}
                  className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-40"
                  data-testid="play-button"
                >
                  {playing ? "暂停" : "播放"}
                </button>
                <button
                  type="button"
                  onClick={stepForward}
                  disabled={events.length === 0}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-40"
                >
                  下一步
                </button>
                <select
                  value={speed}
                  onChange={(e) => setSpeed(Number(e.target.value))}
                  className="rounded-lg border border-slate-300 px-2 py-1.5 text-xs outline-none"
                  aria-label="播放速度"
                >
                  <option value={1500}>慢</option>
                  <option value={900}>正常</option>
                  <option value={350}>快</option>
                </select>
              </div>
            </div>
            <Timeline events={events} currentIndex={playbackIndex} />
          </section>
        </div>

        {/* 右列：答案 + 历史 */}
        <div className="space-y-5">
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900">答案</h2>
              <div className="flex items-center gap-2">
                {doneEvent ? <QualityBadge quality={doneEvent.quality} /> : null}
                <Link
                  to="/monitor"
                  className="text-xs font-medium text-indigo-600 hover:text-indigo-800 hover:underline"
                >
                  数据监测 →
                </Link>
              </div>
            </div>
            {status === "running" ? (
              <div className="text-sm text-slate-400">运行中，等待事件…</div>
            ) : doneEvent ? (
              <>
                <MarkdownAnswer content={doneEvent.final_answer} />
                <dl className="mt-4 grid grid-cols-2 gap-2 border-t border-slate-100 pt-3 text-xs text-slate-500">
                  <div>
                    <dt className="text-slate-400">finish_reason</dt>
                    <dd className="font-mono">{doneEvent.finish_reason || "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-400">迭代轮数</dt>
                    <dd>{doneEvent.iterations}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-400">置信度</dt>
                    <dd>
                      {doneEvent.emergency_report
                        ? `${(doneEvent.emergency_report.confidence * 100).toFixed(0)}%`
                        : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-400">run_id</dt>
                    <dd className="truncate font-mono">{runId ?? "—"}</dd>
                  </div>
                </dl>
                {activeFinding.length > 0 ? (
                  <div className="mt-4 border-t border-slate-100 pt-3">
                    <h3 className="mb-2 text-sm font-medium text-slate-700">引用溯源</h3>
                    <ul className="space-y-2">
                      {activeFinding.map((f, i) => (
                        <li key={i} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs">
                          <p className="text-slate-700">{f.summary}</p>
                          <p className="mt-1 font-mono text-slate-400">
                            {f.source ?? "—"} / {f.chunk_id ?? "无引用"}
                          </p>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </>
            ) : errorEvent ? (
              <div
                className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
                role="alert"
                data-testid="ask-error"
              >
                执行出错：{errorEvent.message}
              </div>
            ) : (
              <div className="text-sm text-slate-400">
                {error
                  ? `出错了：${error}`
                  : "运行一个任务后，这里会展示带引用的 Markdown 答案。"}
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900">历史会话</h2>
              <button
                type="button"
                onClick={clearHistory}
                className="text-xs text-slate-400 hover:text-rose-500"
              >
                清空
              </button>
            </div>
            {history.length === 0 ? (
              <div className="py-4 text-center text-sm text-slate-400">暂无历史记录</div>
            ) : (
              <ul className="space-y-2">
                {history.map((item) => (
                  <li key={item.run_id}>
                    <button
                      type="button"
                      onClick={() => loadHistoryItem(item)}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-left text-xs transition hover:border-indigo-300 hover:bg-indigo-50"
                      data-testid={`history-${item.run_id}`}
                    >
                      <p className="truncate text-slate-700">{item.question}</p>
                      <p className="mt-0.5 text-slate-400">
                        {item.events.length} 个事件 ·{" "}
                        {new Date(item.finished_at).toLocaleString("zh-CN")}
                      </p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </Layout>
  );
}
