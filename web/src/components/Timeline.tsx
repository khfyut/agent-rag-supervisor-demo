// 问答执行时间线：把 AskEvent 渲染成可滚动日志，支持展开详情与当前播放索引高亮。

import { useState } from "react";
import type { AskEvent } from "../types";

function eventTitle(event: AskEvent): string {
  switch (event.type) {
    case "run_start":
      return "任务开始";
    case "supervisor":
      return `Supervisor 派发 → ${event.next}`;
    case "worker":
      return `Worker：${event.worker}`;
    case "reviewer":
      return `Reviewer 质检：${event.verdict === "pass" ? "通过" : "打回"}`;
    case "emergency":
      return "紧急综合（轮次耗尽降级）";
    case "guardrail":
      return `规则门控：${event.passed ? "通过" : "拦截"}`;
    case "done":
      return "任务完成";
    case "error":
      return "执行出错";
  }
}

function eventDetail(event: AskEvent): string[] {
  switch (event.type) {
    case "run_start":
      return [`问题：${event.question}`, `run_id：${event.run_id}`];
    case "supervisor":
      return [event.instructions ? `指令：${event.instructions}` : ""].filter(Boolean);
    case "worker":
      return [
        `发现 ${event.findings.length} 条`,
        event.tool_calls.length > 0
          ? `工具调用：${event.tool_calls.map((t) => t.name).join("、")}`
          : "未调用工具",
        event.self_check ? `自检：${event.self_check}` : "",
        event.error ? `错误：${event.error}` : "",
      ].filter(Boolean);
    case "reviewer":
      return [event.feedback ? `意见：${event.feedback}` : "无修改意见"].filter(Boolean);
    case "emergency":
      return [
        `一句话结论：${event.report.summary}`,
        `置信度：${(event.confidence * 100).toFixed(0)}%`,
      ];
    case "guardrail":
      return [`quality=${event.quality}`, event.reason ? `原因：${event.reason}` : ""].filter(
        Boolean,
      );
    case "done":
      return [
        `finish_reason：${event.finish_reason}`,
        `迭代轮数：${event.iterations}`,
        event.emergency_report
          ? `降级置信度：${(event.emergency_report.confidence * 100).toFixed(0)}%`
          : "",
      ].filter(Boolean);
    case "error":
      return [event.message];
  }
}

export function Timeline({
  events,
  currentIndex,
}: {
  events: AskEvent[];
  currentIndex: number;
}) {
  const [open, setOpen] = useState<number | null>(null);

  if (events.length === 0) {
    return <div className="py-6 text-center text-sm text-slate-400">暂无执行事件</div>;
  }

  return (
    <ol className="timeline-scroll max-h-[420px] space-y-2 overflow-y-auto pr-1" data-testid="timeline">
      {events.map((event, index) => {
        const isCurrent = index === currentIndex;
        const isOpen = open === index;
        const detail = eventDetail(event);
        return (
          <li
            key={index}
            className={`rounded-lg border px-3 py-2 text-sm transition ${
              isCurrent ? "border-indigo-300 bg-indigo-50" : "border-slate-200 bg-white"
            }`}
            data-testid={`timeline-item-${index}`}
          >
            <button
              type="button"
              className="flex w-full items-center justify-between gap-2 text-left"
              onClick={() => setOpen(isOpen ? null : index)}
            >
              <span className={`font-medium ${isCurrent ? "text-indigo-700" : "text-slate-700"}`}>
                {isCurrent ? "▶ " : ""}
                {eventTitle(event)}
              </span>
              <span className="shrink-0 text-xs text-slate-400">{index + 1}</span>
            </button>
            {isOpen && detail.length > 0 ? (
              <div className="mt-1.5 space-y-1 border-t border-slate-100 pt-1.5 text-xs text-slate-500">
                {detail.map((line, i) => (
                  <p key={i} className="break-words">
                    {line}
                  </p>
                ))}
              </div>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
