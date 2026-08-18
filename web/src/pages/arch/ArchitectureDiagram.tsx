// integration: 可切换为共享 NodeGraph 的静态展示模式（agent B 提供）
// 当前为页面层自包含的静态 SVG 架构图（固定拓扑 + 图例）。

const WORKERS = [
  { id: "rag_researcher", label: "rag_researcher", x: 80, y: 150 },
  { id: "sql_analyst", label: "sql_analyst", x: 220, y: 150 },
  { id: "web_searcher", label: "web_searcher", x: 360, y: 150 },
  { id: "stock_analyst", label: "stock_analyst", x: 500, y: 150 },
];

function Box({ x, y, label, sub, color }: { x: number; y: number; label: string; sub?: string; color: string }) {
  const w = label.length > 12 ? 132 : 104;
  const h = sub ? 44 : 34;
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={8} fill={color} stroke="#94a3b8" strokeWidth={1} />
      <text x={x + w / 2} y={y + (sub ? 20 : 21)} textAnchor="middle" fontSize={11} fontWeight={600} fill="#0f172a">
        {label}
      </text>
      {sub ? (
        <text x={x + w / 2} y={y + 34} textAnchor="middle" fontSize={9} fill="#64748b">
          {sub}
        </text>
      ) : null}
    </g>
  );
}

function Arrow({ x1, y1, x2, y2, dashed = false }: { x1: number; y1: number; x2: number; y2: number; dashed?: boolean }) {
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;
  return (
    <>
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#94a3b8" strokeWidth={1.2} strokeDasharray={dashed ? "5 3" : undefined} markerEnd="url(#arrowhead)" />
      <text x={midX + 4} y={midY - 4} fontSize={9} fill="#64748b">
        {dashed ? "降级路径" : ""}
      </text>
    </>
  );
}

export function ArchitectureDiagram() {
  return (
    <div className="overflow-x-auto" data-testid="arch-diagram">
      <svg viewBox="0 0 640 320" className="min-w-[640px]">
        <defs>
          <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#94a3b8" />
          </marker>
        </defs>

        {/* START → supervisor */}
        <Arrow x1={30} y1={40} x2={80} y2={40} />
        <text x={6} y={36} fontSize={10} fill="#64748b">用户</text>
        <Box x={80} y={24} label="supervisor" sub="决策 · 调度" color="#e0e7ff" />

        {/* supervisor → workers */}
        {WORKERS.map((w) => (
          <Arrow key={w.id} x1={150} y1={62} x2={w.x + 40} y2={w.y - 4} />
        ))}
        {WORKERS.map((w) => (
          <Box key={w.id} x={w.x} y={w.y} label={w.label} color="#f1f5f9" />
        ))}

        {/* workers → supervisor（回环） */}
        {WORKERS.map((w) => (
          <Arrow key={`back-${w.id}`} x1={w.x + 40} y1={w.y + 34} x2={150} y2={100} />
        ))}

        {/* supervisor → reviewer */}
        <Arrow x1={150} y1={110} x2={200} y2={250} />
        <Box x={200} y={236} label="reviewer" sub="质量审查 · 可打回" color="#ccfbf1" />
        <Arrow x1={280} y1={270} x2={420} y2={270} />
        <Box x={420} y={252} label="finish" sub="verified 交付" color="#dcfce7" />

        {/* supervisor → emergency → guardrail → END（降级） */}
        <Arrow x1={150} y1={115} x2={520} y2={70} dashed />
        <Box x={490} y={48} label="emergency_synthesizer" sub="轮次耗尽触发" color="#fef3c7" />
        <Arrow x1={570} y1={92} x2={570} y2={130} />
        <Box x={508} y={130} label="guardrail" sub="规则门控 无 LLM" color="#fce7f3" />
        <Arrow x1={570} y1={174} x2={570} y2={210} />
        <Box x={508} y={210} label="END" sub="partial / failed" color="#f1f5f9" />
      </svg>

      <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded bg-indigo-200" /> Supervisor 决策节点</span>
        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded bg-slate-200" /> 角色池 Worker（ReAct 子图）</span>
        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded bg-emerald-200" /> Reviewer 质检</span>
        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded bg-amber-200" /> 降级路径（代码触发）</span>
        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded bg-pink-200" /> Guardrail 规则门控</span>
      </div>
    </div>
  );
}
