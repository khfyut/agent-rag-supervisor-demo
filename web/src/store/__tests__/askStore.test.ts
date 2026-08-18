import { beforeEach, describe, expect, it } from "vitest";
import { useAskStore } from "../useAskStore";
import type { AskEvent } from "../../types";

const EVENTS: AskEvent[] = [
  { type: "run_start", run_id: "r1", question: "q" },
  { type: "supervisor", iteration: 0, next: "rag_researcher", instructions: "i" },
  { type: "done", final_answer: "ok", quality: "verified", finish_reason: "review_pass", iterations: 1, trace: [], findings: [], analysis: [], emergency_report: null, guardrail: null },
];

function resetStore() {
  useAskStore.setState({
    status: "idle",
    question: "",
    runId: null,
    events: [],
    error: null,
    history: [],
    playbackIndex: 0,
    playing: false,
    speed: 900,
  });
}

describe("useAskStore", () => {
  beforeEach(() => {
    localStorage.clear();
    resetStore();
  });

  it("运行状态机：running → 事件累积 → done，并写入 localStorage 历史", () => {
    const runId = useAskStore.getState().startRun("问题？");
    expect(useAskStore.getState().status).toBe("running");
    EVENTS.forEach((e) => useAskStore.getState().appendEvent(e));
    useAskStore.getState().completeRun();
    const state = useAskStore.getState();
    expect(state.status).toBe("done");
    expect(state.events).toHaveLength(EVENTS.length);
    expect(state.history[0].run_id).toBe(runId);
    const stored = JSON.parse(localStorage.getItem("ask-history-v1") ?? "[]");
    expect(stored).toHaveLength(1);
  });

  it("失败路径：error 状态与消息，历史同样落盘", () => {
    useAskStore.getState().startRun("问题？");
    useAskStore.getState().appendEvent({ type: "error", message: "boom" });
    useAskStore.getState().failRun("boom");
    expect(useAskStore.getState().status).toBe("error");
    expect(useAskStore.getState().error).toBe("boom");
    expect(JSON.parse(localStorage.getItem("ask-history-v1") ?? "[]")).toHaveLength(1);
  });

  it("回放状态机：播放/步进到末尾自动停、后退、重置", () => {
    useAskStore.setState({ events: EVENTS, playbackIndex: 0, playing: false });
    useAskStore.getState().startPlayback();
    expect(useAskStore.getState().playing).toBe(true);

    useAskStore.getState().stepForward();
    expect(useAskStore.getState().playbackIndex).toBe(1);
    expect(useAskStore.getState().playing).toBe(true);

    useAskStore.getState().stepForward();
    expect(useAskStore.getState().playbackIndex).toBe(2);
    expect(useAskStore.getState().playing).toBe(false); // 到末尾自动停

    useAskStore.getState().stepBackward();
    expect(useAskStore.getState().playbackIndex).toBe(1);
    expect(useAskStore.getState().playing).toBe(false);

    useAskStore.getState().resetPlayback();
    expect(useAskStore.getState().playbackIndex).toBe(0);
  });

  it("载入历史会话：恢复事件并从头开始回放", () => {
    useAskStore.setState({ history: [{ run_id: "r1", question: "q", events: EVENTS, finished_at: "2026-01-01T00:00:00Z" }] });
    useAskStore.getState().loadHistoryItem(useAskStore.getState().history[0]);
    expect(useAskStore.getState().status).toBe("done");
    expect(useAskStore.getState().events).toHaveLength(EVENTS.length);
    expect(useAskStore.getState().playbackIndex).toBe(0);
  });
});
