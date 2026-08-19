"""SSE（Server-Sent Events）公共工具。

契约：CONTRACT.md 第 2 节。
所有 SSE 统一为 text/event-stream，
事件帧 `event: <name>\ndata: <json>\n\n`；
出错时先发 *_error 事件再结束流。
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
from typing import Any, AsyncIterator, Callable

# 与 app.api 原版保持一致：openai/ollama/deepseek/minimax/mock
ALLOWED_PROVIDERS = {"openai", "ollama", "deepseek", "minimax", "mock", None}


def sse_event(event: str, data: Any) -> str:
    """构造单个 SSE 事件帧。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def normalize_provider(provider: str | None) -> str | None:
    """校验并归一化 provider 字段。非法值抛出 ValueError。"""
    provider = (provider or "").strip().lower() or None
    if provider not in ALLOWED_PROVIDERS:
        raise ValueError(
            f"不支持的 provider: {provider}（可选 openai|ollama|deepseek|minimax|mock）"
        )
    return provider


def spawn(
    fn: Callable[..., None],
    error_event: str,
    *args: Any,
) -> tuple[queue.Queue[tuple[str, dict[str, Any]]], threading.Thread]:
    """把同步图执行放进线程，通过队列向 SSE 流推送事件。

    返回 (events_queue, thread)。线程内部异常会被捕获并以 ``error_event`` 推入队列。
    """
    events: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()

    def target() -> None:
        try:
            fn(*args, events)
        except Exception as exc:  # noqa: BLE001 - 统一转成 *_error 事件
            events.put((error_event, {"message": f"{type(exc).__name__}: {exc}"}))

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return events, thread


async def drain(
    events: queue.Queue[tuple[str, dict[str, Any]]],
    thread: threading.Thread,
    terminal: set[str],
) -> AsyncIterator[str]:
    """异步消费队列直到收到终止事件；线程异常退出时兜底发 error。

    ``terminal`` 是视为流终止的事件名集合（done / *_done / *_error / error）。
    """
    while True:
        try:
            event, data = events.get_nowait()
            yield sse_event(event, data)
            if event in terminal:
                return
        except queue.Empty:
            if not thread.is_alive():
                yield sse_event("error", {"message": "服务内部错误：执行线程异常退出"})
                return
            await asyncio.sleep(0.05)