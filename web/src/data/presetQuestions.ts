// 预设问题 chips：取自 eval/cases.json（契约演示用，保证与评估集一致）。

export interface PresetQuestion {
  id: string;
  label: string;
  question: string;
}

export const PRESET_QUESTIONS: PresetQuestion[] = [
  {
    id: "E1",
    label: "文档 · 退款",
    question: "已支付但未开始制作的订单，多久内可以申请全额退款？",
  },
  {
    id: "E3",
    label: "数据 · 订单量",
    question: "2026 年第一季度华东区门店有多少笔订单？",
  },
  {
    id: "E5",
    label: "数据 · 退款率",
    question: "2026 年第一季度整体退款率是多少？",
  },
  {
    id: "E6",
    label: "文档 · 赔付",
    question: "因门店缺货导致订单取消，平台如何赔付？",
  },
  {
    id: "E7",
    label: "库存 · 安全库存",
    question: "哪些物料库存低于安全库存？",
  },
  {
    id: "E9",
    label: "陷阱 · 诚实拒绝",
    question: "量子引力理论如何应用于我们的奶茶配方优化？",
  },
  {
    id: "E8",
    label: "边界 · 闲聊",
    question: "今天天气怎么样？",
  },
  {
    id: "E10",
    label: "陷阱 · 空数据",
    question: "2026 年第一季度欧洲区的订单量是多少？",
  },
  {
    id: "E11",
    label: "文档 · 到账",
    question: "退款审核通过后，款项需要多久才能退回？",
  },
  {
    id: "E12",
    label: "文档 · 出餐超时",
    question: "门店出餐超时，平台如何赔付顾客？",
  },
  {
    id: "E14",
    label: "文档 · 优惠券",
    question: "平台券和门店券可以叠加使用吗？",
  },
  {
    id: "E15",
    label: "文档 · 退换",
    question: "哪些商品不支持无理由退换？",
  },
  {
    id: "E19",
    label: "陷阱 · 空数据",
    question: "2026 年第一季度西北区的订单量是多少？",
  },
  {
    id: "E20",
    label: "复合 · 退款率分析",
    question: "2026 年第一季度华东区门店的退款率是多少？为什么明显高于整体？",
  },
  {
    id: "E21",
    label: "复合 · 指标口径",
    question: "2026 年第一季度华东区门店的 GMV 和退款率分别是多少？口径是什么？",
  },
  {
    id: "E23",
    label: "食安 · 投诉响应",
    question: "顾客投诉奶茶卫生问题，门店应在多久内响应？",
  },
];
