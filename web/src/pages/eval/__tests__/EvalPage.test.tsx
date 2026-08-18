import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import EvalPage from "../../EvalPage";
import { buildMockReport, MOCK_EVAL_EVENTS, MOCK_REPORTS_META } from "../../local/localMock";

function sseResponse(events: Array<{ type: string; [k: string]: unknown }>) {
  const text = events
    .map(({ type, ...data }) => `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`)
    .join("");
  return new Response(text, { status: 200 });
}

describe("EvalPage", () => {
  beforeEach(() => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/api/eval/reports") {
        return new Response(JSON.stringify({ reports: MOCK_REPORTS_META }), { status: 200 });
      }
      if (url === "/api/eval/reports/report_20260814_151708.json") {
        return new Response(JSON.stringify(buildMockReport()), { status: 200 });
      }
      if (url === "/api/eval/run") {
        return sseResponse(MOCK_EVAL_EVENTS as unknown as Array<{ type: string }>);
      }
      return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染指标卡与报告列表，展开用例详情", async () => {
    render(
      <MemoryRouter>
        <EvalPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByTestId("metric-card")).toHaveLength(8));
    expect(screen.getAllByTestId("report-item").length).toBeGreaterThan(0);
    await waitFor(() => expect(screen.getAllByTestId("case-row").length).toBeGreaterThan(0));
    fireEvent.click(screen.getAllByTestId("case-row")[0]);
    await waitFor(() => expect(screen.getByText(/最终回答/)).toBeTruthy());
  });

  it("运行评估弹窗：提交后展示进度并完成", async () => {
    render(
      <MemoryRouter>
        <EvalPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByTestId("metric-card")).toHaveLength(8));
    fireEvent.click(screen.getByTestId("open-eval-run"));
    expect(screen.getByTestId("run-eval-dialog")).toBeTruthy();
    fireEvent.change(screen.getByTestId("eval-provider"), { target: { value: "mock" } });
    fireEvent.click(screen.getByTestId("eval-run-submit"));
    await waitFor(() => expect(screen.getByText(/评估完成，报告已生成/)).toBeTruthy(), {
      timeout: 3000,
    });
  });
});
