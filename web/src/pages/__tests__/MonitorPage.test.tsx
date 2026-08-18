import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MonitorPage from "../MonitorPage";

const RUN_META = {
  run_id: "run123",
  question: "华东区门店退款率是多少？",
  provider: "mock",
  created_at: "2026-08-17T10:00:00",
  status: "done",
  iterations: 3,
  quality: "verified",
  finish_reason: "review_pass",
};

const RUN = {
  ...RUN_META,
  final_answer: "华东区退款率约 50%，明显高于整体。",
  error: "",
  trace: [],
  steps: [
    {
      node: "supervisor",
      iteration: 0,
      next: "sql_analyst",
      instructions: "计算华东区门店退款率",
      input: { question: "华东区门店退款率是多少？", findings_summary: [], draft_preview: "" },
      output: { next: "sql_analyst", instructions: "计算华东区门店退款率", draft: null, final_answer: null },
    },
    {
      node: "worker",
      worker: "sql_analyst",
      instructions: "计算华东区门店退款率",
      input: "用户问题：华东区门店退款率是多少？\n主管指令：计算华东区门店退款率",
      output: {
        findings: [{ summary: "华东区 2 笔订单，1 笔退款" }],
        worker_report: { self_check: "ok" },
      },
      log: [
        {
          role: "ai",
          content: "我需要先查询华东区订单数据",
          tool_calls: [{ name: "query_sql", args: { sql: "SELECT region FROM orders" } }],
        },
        { role: "tool", name: "query_sql", content: '[{"region": "华东", "n": 2, "refunded": 1}]' },
      ],
      tool_calls: [
        {
          name: "query_sql",
          args: { sql: "SELECT region, COUNT(*) FROM orders WHERE created_at BETWEEN '2026-01-01' AND '2026-03-31' GROUP BY region" },
          result: '[{"region": "华东", "n": 2, "refunded": 1}]',
        },
      ],
      findings: [{ summary: "华东区 2 笔订单，1 笔退款", chunk_id: "", source: "" }],
      self_check: "ok",
      error: "",
    },
    {
      node: "reviewer",
      verdict: "pass",
      feedback: "",
      input: { question: "华东区门店退款率是多少？", draft: "草稿" },
      output: { verdict: "pass", feedback: "", revised_report: "华东区退款率约 50%。" },
    },
  ],
};

describe("MonitorPage", () => {
  beforeEach(() => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/api/monitor/runs") {
        return new Response(JSON.stringify({ runs: [RUN_META] }), { status: 200 });
      }
      if (url === "/api/monitor/runs/run123") {
        return new Response(JSON.stringify({ run: RUN }), { status: 200 });
      }
      return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染运行列表并展示选中运行的完整 Agent 思考过程", async () => {
    render(
      <MemoryRouter>
        <MonitorPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByTestId("monitor-run-item")).toBeTruthy());
    expect(screen.getByText("华东区门店退款率是多少？")).toBeTruthy();

    fireEvent.click(screen.getByTestId("monitor-run-item"));
    await waitFor(() => expect(screen.getAllByTestId("monitor-step").length).toBeGreaterThan(0));

    expect(screen.getByText("主管决策")).toBeTruthy();
    expect(screen.getByText("专家执行")).toBeTruthy();
    expect(screen.getByText("质检")).toBeTruthy();
    expect(screen.getAllByText("query_sql").length).toBeGreaterThan(0);
    expect(screen.getByText("返回结果")).toBeTruthy();
    expect(screen.getByText("最终交付")).toBeTruthy();
    expect(screen.getAllByText(/华东区退款率约 50%/).length).toBeGreaterThan(0);

    // 输入 / 输出 / 思考日志
    expect(screen.getAllByText("输入").length).toBeGreaterThan(0);
    expect(screen.getAllByText("输出").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText("思考过程（2 条消息）"));
    await waitFor(() => expect(screen.getByText("我需要先查询华东区订单数据")).toBeTruthy());
  });
});
