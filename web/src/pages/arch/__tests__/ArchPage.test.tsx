import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ArchPage from "../../ArchPage";
import { MOCK_WORKERS } from "../../local/localMock";

describe("ArchPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/workers") {
          return new Response(JSON.stringify(MOCK_WORKERS), { status: 200 });
        }
        if (url === "/api/status") {
          return new Response(
            JSON.stringify({ provider: "mock", model: "gpt-4o-mini", kb_ready: true, db_ready: true, kb_chunks: 12, reports_count: 3 }),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染架构图、角色池、对比表与降级闭环", async () => {
    render(
      <MemoryRouter>
        <ArchPage />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("arch-diagram")).toBeTruthy();
    expect(screen.getByTestId("compare-table")).toBeTruthy();
    expect(screen.getByTestId("degradation-loop")).toBeTruthy();
    await waitFor(() => expect(screen.getAllByTestId("worker-pool").length).toBe(1));
    expect(screen.getByText(/知识库研究员/)).toBeTruthy();
    expect(screen.getByText(/search_knowledge/)).toBeTruthy();
    expect(screen.getAllByTestId("status-bar").length).toBe(1);
  });
});
