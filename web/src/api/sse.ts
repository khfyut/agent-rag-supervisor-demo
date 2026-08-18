// 手写 SSE 客户端：fetch + ReadableStream，按 `event: <name>\ndata: <json>\n\n` 解析。
// 契约见 CONTRACT.md 第 3 节；导出签名与页面层 local/localApi.ts 对齐，方便整合替换。

/** 从响应流中按 SSE 规范解析事件（兼容 \r\n、多行 data）。 */
export async function parseSseStream(
  response: Response,
  onEvent: (eventName: string, data: unknown) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.body) {
    throw new Error("响应没有可读流");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  const dispatch = (raw: string) => {
    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of raw.split("\n")) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).replace(/^ /, ""));
      }
    }
    if (dataLines.length === 0) return;
    try {
      onEvent(eventName, JSON.parse(dataLines.join("\n")));
    } catch {
      onEvent(eventName, dataLines.join("\n"));
    }
  };

  for (;;) {
    if (signal?.aborted) break;
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      if (block.trim()) dispatch(block.replace(/\r/g, ""));
    }
  }
  if (buffer.trim()) dispatch(buffer.replace(/\r/g, "").trim());
}

/** POST 一个 SSE 端点，返回 AbortController 以便取消。 */
export function postSse(
  url: string,
  body: object,
  onEvent: (eventName: string, data: unknown) => void,
): AbortController {
  const controller = new AbortController();
  void (async () => {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!resp.ok) {
      let detail = `HTTP ${resp.status}`;
      try {
        const payload = (await resp.json()) as { detail?: string };
        if (payload.detail) detail = payload.detail;
      } catch {
        /* 非 JSON 错误体，保留状态码 */
      }
      onEvent("error", { message: detail });
      return;
    }
    try {
      await parseSseStream(resp, onEvent, controller.signal);
    } catch (err) {
      if (!controller.signal.aborted) {
        onEvent("error", {
          message: err instanceof Error ? err.message : String(err),
        });
      }
    }
  })();
  return controller;
}
