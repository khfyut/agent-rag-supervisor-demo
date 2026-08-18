import { Layout, Section } from "../components";
import { ArchitectureDiagram } from "./arch/ArchitectureDiagram";
import { CompareTable } from "./arch/CompareTable";
import { DegradationLoop } from "./arch/DegradationLoop";
import { WorkerPool } from "./arch/WorkerPool";

export default function ArchPage() {
  return (
    <Layout>
      <div className="space-y-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">架构讲解</h1>
          <p className="mt-1 text-sm text-slate-500">
            为什么这是 Agent 而不是 Workflow：控制权、自主循环、动态路径与自修复
          </p>
        </div>

        <Section title="系统架构图" desc="Supervisor 模式：所有 Worker 与 Reviewer 都回到 Supervisor，构成自主循环">
          <ArchitectureDiagram />
        </Section>

        <Section title="角色池（预注册，动态选择）" desc="角色由代码预定义，Supervisor 运行时只能从池中「选择」而不能「凭空生成」——安全边界可控">
          <WorkerPool />
        </Section>

        <Section title="Agent vs Workflow" desc="同一个「流程」因为控制权归属不同，性质完全不同">
          <CompareTable />
        </Section>

        <Section title="降级质量闭环" desc="轮次耗尽时系统不交半成品，而是走 emergency_synthesizer + guardrail 的强制路径">
          <DegradationLoop />
        </Section>

        <Section title="面试讲解要点" desc="怎么把这个项目讲清楚">
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-slate-600">
            <li>先用「Agent vs Workflow 判断标准」开场，再拿本项目当例子证。</li>
            <li>讲 Supervisor 模式时画「循环」而不是「流水线」——Worker / Reviewer 都回到 Supervisor。</li>
            <li>讲 RAG 时强调：检索是 Agent 的工具，不是固定的前置步骤。</li>
            <li>讲评估时准备 bad case 故事：引用编造 → Reviewer 打回 → 修正后打回率下降。</li>
            <li>讲场景选型：为什么是连锁奶茶店——平台规则、食安合规、门店数据三方冲突，让 Supervisor 的「裁决」和 Reviewer/Guardrail 的「否决」成为业务必要而非装饰。</li>
            <li>讲角色池时主动说明「动态选择 vs 自由生成」的取舍：自由生成不可控（安全边界、评估、成本全崩）。</li>
          </ul>
        </Section>
      </div>
    </Layout>
  );
}
