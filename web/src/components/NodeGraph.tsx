// 自定义 SVG 执行图：Supervisor → 角色池 Worker → Reviewer → Emergency → Guardrail → END 的固定拓扑。
// 节点随运行事件点亮（activeNode），点击节点可查看详情。

export type GraphNodeId =
  | "supervisor"
  | "rag_researcher"
  | "sql_analyst"
  | "web_searcher"
  | "stock_analyst"
  | "reviewer"
  | "emergency_synthesizer"
  | "guardrail"
  | "END";

interface NodeDef {
  id: GraphNodeId;
  label: string;
  sub: string;
  x: number;
  y: number;
  color: string;
}

const NODE_DEFS: NodeDef[] = [
  { id: "supervisor", label: "主管", sub: "Supervisor", x: 380, y: 55, color: "#6366f1" },
  { id: "rag_researcher", label: "知识库研究员", sub: "rag_researcher", x: 100, y: 185, color: "#0ea5e9" },
  { id: "sql_analyst", label: "数据分析师", sub: "sql_analyst", x: 275, y: 185, color: "#0ea5e9" },
  { id: "web_searcher", label: "网络研究员", sub: "web_searcher", x: 450, y: 185, color: "#0ea5e9" },
  { id: "stock_analyst", label: "库存分析师", sub: "stock_analyst", x: 625, y: 185, color: "#0ea5e9" },
  { id: "reviewer", label: "质检员", sub: "Reviewer", x: 100, y: 330, color: "#f59e0b" },
  { id: "emergency_synthesizer", label: "紧急综合", sub: "Emergency", x: 450, y: 330, color: "#8b5cf6" },
  { id: "guardrail", label: "规则门控", sub: "Guardrail", x: 450, y: 455, color: "#f43f5e" },
  { id: "END", label: "结束", sub: "END", x: 640, y: 455, color: "#64748b" },
];

const EDGES: Array<[GraphNodeId, GraphNodeId, "normal" | "dashed"]> = [
  ["supervisor", "rag_researcher", "normal"],
  ["supervisor", "sql_analyst", "normal"],
  ["supervisor", "web_searcher", "normal"],
  ["supervisor", "stock_analyst", "normal"],
  ["rag_researcher", "supervisor", "normal"],
  ["sql_analyst", "supervisor", "normal"],
  ["web_searcher", "supervisor", "normal"],
  ["stock_analyst", "supervisor", "normal"],
  ["supervisor", "reviewer", "normal"],
  ["reviewer", "supervisor", "normal"],
  ["supervisor", "emergency_synthesizer", "dashed"],
  ["emergency_synthesizer", "guardrail", "normal"],
  ["guardrail", "END", "normal"],
  ["supervisor", "END", "dashed"],
];

function point(id: GraphNodeId): { x: number; y: number } {
  const def = NODE_DEFS.find((n) => n.id === id);
  return def ? { x: def.x, y: def.y } : { x: 0, y: 0 };
}

export function NodeGraph({
  activeNode,
  onNodeClick,
  staticMode = false,
}: {
  activeNode?: string | null;
  onNodeClick?: (node: string) => void;
  staticMode?: boolean;
}) {
  const active = staticMode ? null : activeNode;
  return (
    <svg
      viewBox="0 0 760 520"
      className="w-full rounded-xl border border-slate-200 bg-white"
      role="img"
      aria-label="多 Agent 执行图"
      data-testid="node-graph"
    >
      {/* 边 */}
      {EDGES.map(([from, to, kind]) => {
        const a = point(from);
        const b = point(to);
        const highlighted = active === from || active === to;
        return (
          <line
            key={`${from}-${to}`}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke={highlighted ? "#6366f1" : "#cbd5e1"}
            strokeWidth={highlighted ? 2.5 : 1.5}
            strokeDasharray={kind === "dashed" ? "6 4" : undefined}
            strokeLinecap="round"
          />
        );
      })}

      {/* 节点 */}
      {NODE_DEFS.map((node) => {
        const isActive = active === node.id;
        const radius = 20;
        return (
          <g
            key={node.id}
            onClick={() => onNodeClick?.(node.id)}
            className={onNodeClick ? "cursor-pointer" : undefined}
            data-testid={`graph-node-${node.id}`}
          >
            <circle
              cx={node.x}
              cy={node.y}
              r={radius}
              fill={isActive ? node.color : "#ffffff"}
              stroke={node.color}
              strokeWidth={isActive ? 3 : 2}
              className={isActive ? "node-active" : undefined}
            />
            <circle cx={node.x} cy={node.y} r={4} fill={node.color} />
            <text
              x={node.x}
              y={node.y + radius + 18}
              textAnchor="middle"
              fontSize="12"
              fontWeight={isActive ? 700 : 500}
              fill={isActive ? node.color : "#334155"}
            >
              {node.label}
            </text>
            <text
              x={node.x}
              y={node.y + radius + 33}
              textAnchor="middle"
              fontSize="9"
              fill="#94a3b8"
            >
              {node.sub}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
