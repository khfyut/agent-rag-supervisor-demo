// 问答运行状态 + 历史回放（localStorage 持久化，回放不重跑 LLM）。

import { create } from "zustand";
import type { AskEvent } from "../types";

export type AskStatus = "idle" | "running" | "done" | "error";

export interface AskHistoryItem {
  run_id: string;
  question: string;
  events: AskEvent[];
  finished_at: string;
}

const HISTORY_KEY = "ask-history-v1";

function loadHistory(): AskHistoryItem[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as AskHistoryItem[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persistHistory(items: AskHistoryItem[]) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(items));
  } catch {
    /* localStorage 不可用时静默降级 */
  }
}

interface AskState {
  status: AskStatus;
  question: string;
  runId: string | null;
  events: AskEvent[];
  error: string | null;
  history: AskHistoryItem[];
  playbackIndex: number;
  playing: boolean;
  speed: number;

  startRun: (question: string) => string;
  appendEvent: (event: AskEvent) => void;
  completeRun: () => void;
  failRun: (message: string) => void;
  reset: () => void;
  loadHistoryItem: (item: AskHistoryItem) => void;
  clearHistory: () => void;
  startPlayback: () => void;
  pausePlayback: () => void;
  stepForward: () => void;
  stepBackward: () => void;
  setSpeed: (speed: number) => void;
  resetPlayback: () => void;
}

function makeRunId(): string {
  return `run-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export const useAskStore = create<AskState>((set, get) => ({
  status: "idle",
  question: "",
  runId: null,
  events: [],
  error: null,
  history: loadHistory(),
  playbackIndex: 0,
  playing: false,
  speed: 900,

  startRun: (question) => {
    const runId = makeRunId();
    set({
      status: "running",
      question,
      runId,
      events: [],
      error: null,
      playbackIndex: 0,
      playing: false,
    });
    return runId;
  },

  appendEvent: (event) => {
    set((state) => {
      const events = [...state.events, event];
      // 实时运行时始终展示最新事件
      const playbackIndex = state.playing ? state.playbackIndex : events.length - 1;
      return { events, playbackIndex };
    });
  },

  completeRun: () => {
    const { runId, question, events } = get();
    const item: AskHistoryItem = {
      run_id: runId ?? makeRunId(),
      question,
      events,
      finished_at: new Date().toISOString(),
    };
    const history = [item, ...get().history].slice(0, 50);
    persistHistory(history);
    set({
      status: "done",
      history,
      playbackIndex: Math.max(0, events.length - 1),
      playing: false,
    });
  },

  failRun: (message) => {
    const { runId, question, events } = get();
    const item: AskHistoryItem = {
      run_id: runId ?? makeRunId(),
      question,
      events,
      finished_at: new Date().toISOString(),
    };
    const history = [item, ...get().history].slice(0, 50);
    persistHistory(history);
    set({
      status: "error",
      error: message,
      history,
      playbackIndex: Math.max(0, events.length - 1),
      playing: false,
    });
  },

  reset: () =>
    set({
      status: "idle",
      question: "",
      runId: null,
      events: [],
      error: null,
      playbackIndex: 0,
      playing: false,
    }),

  loadHistoryItem: (item) =>
    set({
      status: "done",
      question: item.question,
      runId: item.run_id,
      events: item.events,
      error: null,
      playbackIndex: 0,
      playing: false,
    }),

  clearHistory: () => {
    persistHistory([]);
    set({ history: [] });
  },

  startPlayback: () => {
    const { events } = get();
    if (events.length === 0) return;
    if (get().playbackIndex >= events.length - 1) {
      set({ playbackIndex: 0, playing: true });
    } else {
      set({ playing: true });
    }
  },

  pausePlayback: () => set({ playing: false }),

  stepForward: () => {
    const { events, playing, playbackIndex } = get();
    if (events.length === 0) return;
    const next = Math.min(playbackIndex + 1, events.length - 1);
    set({ playbackIndex: next, playing: next < events.length - 1 ? playing : false });
  },

  stepBackward: () => {
    const { playbackIndex } = get();
    set({ playbackIndex: Math.max(0, playbackIndex - 1), playing: false });
  },

  setSpeed: (speed) => set({ speed }),

  resetPlayback: () => set({ playbackIndex: 0, playing: false }),
}));
