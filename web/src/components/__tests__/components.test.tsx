import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarkdownAnswer } from "../MarkdownAnswer";
import { MetricCard } from "../MetricCard";
import { NodeGraph } from "../NodeGraph";
import { QualityBadge } from "../QualityBadge";
import { Timeline } from "../Timeline";
import { CitationBadge, Empty, ErrorNotice, Loading, ProgressBar, Section, StatusPill } from "../ui";
import type { AskEvent } from "../../types";

describe("NodeGraph", () => {
  it("渲染固定拓扑节点，active 节点带脉冲类", () => {
    const { container } = render(<NodeGraph activeNode="supervisor" />);
    expect(screen.getByText("主管")).toBeInTheDocument();
    expect(screen.getByText("知识库研究员")).toBeInTheDocument();
    expect(screen.getByText("规则门控")).toBeInTheDocument();
    const activeCircle = container.querySelector(
      '[data-testid="graph-node-supervisor"] circle.node-active',
    );
    expect(activeCircle).not.toBeNull();
  });

  it("staticMode 下不点亮任何节点", () => {
    const { container } = render(<NodeGraph activeNode="supervisor" staticMode />);
    expect(container.querySelector("circle.node-active")).toBeNull();
  });
});

describe("QualityBadge", () => {
  it("三态标签正确", () => {
    const { rerender } = render(<QualityBadge quality="verified" />);
    expect(screen.getByText("verified 已验证")).toBeInTheDocument();
    rerender(<QualityBadge quality="partial" />);
    expect(screen.getByText("partial 阶段快报")).toBeInTheDocument();
    rerender(<QualityBadge quality="failed" />);
    expect(screen.getByText("failed 诚实降级")).toBeInTheDocument();
  });

  it("未知值兜底显示原文", () => {
    render(<QualityBadge quality="weird" />);
    expect(screen.getByText("quality=weird")).toBeInTheDocument();
  });
});

describe("MetricCard", () => {
  it("渲染标题/数值/提示", () => {
    render(<MetricCard title="任务成功率" value="85.0%" hint="共 20 例" />);
    expect(screen.getByText("任务成功率")).toBeInTheDocument();
    expect(screen.getByText("85.0%")).toBeInTheDocument();
    expect(screen.getByText("共 20 例")).toBeInTheDocument();
  });
});

describe("MarkdownAnswer", () => {
  it("渲染 GFM Markdown（标题/列表）", () => {
    render(<MarkdownAnswer content={"# 结论\n\n- 甲\n- 乙"} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("结论");
    expect(screen.getByText("甲")).toBeInTheDocument();
  });

  it("空内容显示占位", () => {
    render(<MarkdownAnswer content="" />);
    expect(screen.getByText("（暂无内容）")).toBeInTheDocument();
  });
});

describe("Timeline", () => {
  it("渲染事件标题并高亮当前项", () => {
    const events: AskEvent[] = [
      { type: "run_start", run_id: "r1", question: "q" },
      { type: "supervisor", iteration: 0, next: "rag_researcher", instructions: "i" },
    ];
    render(<Timeline events={events} currentIndex={1} />);
    expect(screen.getByText("任务开始")).toBeInTheDocument();
    expect(screen.getByText(/Supervisor 派发 → rag_researcher/)).toBeInTheDocument();
    expect(screen.getByTestId("timeline-item-1")).toHaveClass("border-indigo-300");
  });

  it("空事件列表显示占位", () => {
    render(<Timeline events={[]} currentIndex={0} />);
    expect(screen.getByText("暂无执行事件")).toBeInTheDocument();
  });
});

describe("ui 小组件", () => {
  it("StatusPill 就绪/未就绪", () => {
    const { rerender } = render(<StatusPill ok label="KB 就绪" />);
    expect(screen.getByText("KB 就绪")).toBeInTheDocument();
    rerender(<StatusPill ok={false} label="KB 未就绪" />);
    expect(screen.getByText("KB 未就绪")).toBeInTheDocument();
  });

  it("Section / ProgressBar / CitationBadge / Loading / Empty / ErrorNotice", () => {
    render(
      <Section title="区块" desc="说明">
        <ProgressBar current={1} total={4} label="重建中" detail="文件 2/4" />
        <CitationBadge valid />
        <Loading text="加载中…" />
        <Empty text="暂无" />
        <ErrorNotice message="boom" />
      </Section>,
    );
    expect(screen.getByText("区块")).toBeInTheDocument();
    expect(screen.getByText("重建中")).toBeInTheDocument();
    expect(screen.getByText("✓ 引用有效")).toBeInTheDocument();
    expect(screen.getByText("加载中…")).toBeInTheDocument();
    expect(screen.getByText("暂无")).toBeInTheDocument();
    expect(screen.getByText("出错了：boom")).toBeInTheDocument();
  });
});
