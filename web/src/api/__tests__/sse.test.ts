import { describe, expect, it, vi } from "vitest";
import { parseSseStream, postSse } from "../sse";

function sseResponse(blocks: string): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(blocks));
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

describe("parseSseStream", () => {
  it("按空行分块解析 event/data，JSON 反序列化", async () => {
    const onEvent = vi.fn();
    const raw =
      'event: run_start\ndata: {"run_id":"r1","question":"q"}\n\n' +
      'event: supervisor\ndata: {"iteration":0,"next":"rag_researcher","instructions":"i"}\n\n';
    await parseSseStream(sseResponse(raw), onEvent);
    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent).toHaveBeenNthCalledWith(1, "run_start", { run_id: "r1", question: "q" });
    expect(onEvent).toHaveBeenNthCalledWith(2, "supervisor", {
      iteration: 0,
      next: "rag_researcher",
      instructions: "i",
    });
  });

  it("兼容 CRLF 与跨块拆包", async () => {
    const onEvent = vi.fn();
    const raw = "event: worker\r\ndata: {\"worker\":\"sql_analyst\"";
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        const bytes = new TextEncoder().encode(raw);
        // 分两次投递，模拟网络拆包
        controller.enqueue(bytes.slice(0, 12));
        controller.enqueue(bytes.slice(12));
        controller.enqueue(new TextEncoder().encode(",\"findings\":[]}\n\n"));
        controller.close();
      },
    });
    await parseSseStream(new Response(stream), onEvent);
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith("worker", { worker: "sql_analyst", findings: [] });
  });

  it("空块与无 data 的块不发事件", async () => {
    const onEvent = vi.fn();
    await parseSseStream(sseResponse(": keepalive\n\n\n\n"), onEvent);
    expect(onEvent).not.toHaveBeenCalled();
  });

  it("data 非 JSON 时原样透传", async () => {
    const onEvent = vi.fn();
    await parseSseStream(sseResponse('event: message\ndata: hello\n\n'), onEvent);
    expect(onEvent).toHaveBeenCalledWith("message", "hello");
  });

  it("signal 中止时停止读取", async () => {
    const onEvent = vi.fn();
    const controller = new AbortController();
    controller.abort();
    await parseSseStream(sseResponse('event: run_start\ndata: {}\n\n'), onEvent, controller.signal);
    expect(onEvent).not.toHaveBeenCalled();
  });
});

describe("postSse", () => {
  it("非 2xx 时发出 error 事件并携带 detail", async () => {
    const onEvent = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "知识库未就绪" }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    postSse("/api/ask", { question: "q" }, onEvent);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(onEvent).toHaveBeenCalledWith("error", { message: "知识库未就绪" });
    vi.unstubAllGlobals();
  });

  it("正常流按事件逐条回调", async () => {
    const onEvent = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(sseResponse('event: done\ndata: {"final_answer":"ok"}\n\n')),
    );
    postSse("/api/ask", { question: "q" }, onEvent);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(onEvent).toHaveBeenCalledWith("done", { final_answer: "ok" });
    vi.unstubAllGlobals();
  });
});
