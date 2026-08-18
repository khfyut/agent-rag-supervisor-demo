const ROWS: Array<{ dim: string; agent: string; workflow: string }> = [
  {
    dim: "控制权归属",
    agent: "下一步去哪由 Supervisor（LLM）在运行时决定",
    workflow: "路径由代码写死，节点按固定顺序执行",
  },
  {
    dim: "自主循环",
    agent: "Supervisor → Worker → Supervisor 循环，直到模型判断 finish",
    workflow: "每个节点通常只执行一次，无决策回环",
  },
  {
    dim: "动态路径",
    agent: "同一问题多次运行可能走不同路径（检索几次、要不要打回）",
    workflow: "所有输入走同一条固定流水线",
  },
  {
    dim: "出错自修复",
    agent: "Reviewer 打回 → Supervisor 带反馈重新派发，工具失败可转派",
    workflow: "错误只能中断或按预设分支处理",
  },
  {
    dim: "适用场景",
    agent: "开放任务、多工具组合、需要判断与协作的问题",
    workflow: "稳定、可预期的批量处理（如 ETL、校验链）",
  },
];

export function CompareTable() {
  return (
    <div className="overflow-x-auto" data-testid="compare-table">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs text-slate-500">
            <th className="py-2 pr-3 w-32">维度</th>
            <th className="py-2 pr-3">Agent（本项目）</th>
            <th className="py-2 pr-3">Workflow</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((r) => (
            <tr key={r.dim} className="border-b border-slate-100 align-top">
              <td className="py-2.5 pr-3 font-medium text-slate-800">{r.dim}</td>
              <td className="py-2.5 pr-3 text-slate-600">{r.agent}</td>
              <td className="py-2.5 pr-3 text-slate-600">{r.workflow}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
