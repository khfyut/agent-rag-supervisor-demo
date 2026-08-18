import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import KbPage from "../../KbPage";
import { MOCK_DOCS, MOCK_KB_BUILD_EVENTS, MOCK_SEARCH_RESULTS } from "../../local/localMock";
import { validateFile } from "../UploadZone";

function sseResponse(events: Array<{ type: string; [k: string]: unknown }>) {
  const text = events
    .map(({ type, ...data }) => `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`)
    .join("");
  return new Response(text, { status: 200 });
}

describe("validateFile", () => {
  it("拒绝非 .md/.txt 文件", () => {
    const f = new File(["x"], "evil.exe", { type: "application/octet-stream" });
    expect(validateFile(f)).toContain("仅支持");
  });

  it("拒绝超过 1MB 的文件", () => {
    const big = new File([new Uint8Array(1024 * 1024 + 1)], "big.md", { type: "text/markdown" });
    expect(validateFile(big)).toContain("1MB");
  });

  it("接受合法 .md / .txt", () => {
    expect(validateFile(new File(["a"], "a.md", { type: "text/markdown" }))).toBeNull();
    expect(validateFile(new File(["a"], "a.txt", { type: "text/plain" }))).toBeNull();
  });
});

describe("KbPage", () => {
  beforeEach(() => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      if (url === "/api/kb/docs" && method === "GET") {
        return new Response(JSON.stringify({ docs: MOCK_DOCS, dirty: true }), { status: 200 });
      }
      if (url === "/api/kb/rebuild") {
        return sseResponse(MOCK_KB_BUILD_EVENTS as unknown as Array<{ type: string }>);
      }
      if (url === "/api/kb/search") {
        return new Response(JSON.stringify({ results: MOCK_SEARCH_RESULTS }), { status: 200 });
      }
      if (url.startsWith("/api/kb/docs/") && method === "DELETE") {
        return new Response(
          JSON.stringify({ docs: MOCK_DOCS.filter((d) => d.name !== decodeURIComponent(url.split("/").pop() ?? "")), dirty: true }),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染文档列表与需重建横幅", async () => {
    render(
      <MemoryRouter>
        <KbPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByTestId("doc-row")).toHaveLength(3));
    expect(screen.getByTestId("dirty-banner")).toBeTruthy();
    expect(screen.getByText(/门店运营手册\.md/)).toBeTruthy();
  });

  it("删除需要二次确认并调用 DELETE", async () => {
    render(
      <MemoryRouter>
        <KbPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByTestId("doc-row")).toHaveLength(3));
    fireEvent.click(screen.getAllByTestId("delete-doc")[0]);
    expect(screen.getByTestId("delete-confirm")).toBeTruthy();
    fireEvent.click(screen.getByTestId("confirm-delete"));
    await waitFor(() => expect(screen.getAllByTestId("doc-row")).toHaveLength(2));
  });

  it("重建向量库展示逐文件进度并完成", async () => {
    render(
      <MemoryRouter>
        <KbPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByTestId("doc-row")).toHaveLength(3));
    fireEvent.click(screen.getByTestId("rebuild-button"));
    await waitFor(() => expect(screen.getByTestId("rebuild-done")).toBeTruthy(), {
      timeout: 3000,
    });
    expect(screen.getByText(/重建完成：3 个文档/)).toBeTruthy();
  });

  it("检索测试台展示 top-k 结果与引用核验徽标", async () => {
    render(
      <MemoryRouter>
        <KbPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByTestId("doc-row")).toHaveLength(3));
    fireEvent.change(screen.getByTestId("search-query"), {
      target: { value: "退款" },
    });
    fireEvent.click(screen.getByTestId("search-button"));
    await waitFor(() => expect(screen.getAllByTestId("search-result-card")).toHaveLength(3));
    expect(screen.getAllByTestId("citation-badge").length).toBe(3);
    expect(screen.getAllByText(/引用有效/).length).toBe(2);
    expect(screen.getAllByText(/引用缺失/).length).toBe(1);
  });
});
