import type { Step } from "../api";

const FIELD_LABELS: Record<string, string> = {
  DEST: "目的地コード",
  DEPTDATE: "出発日",
  RETDATE: "帰着日",
  DAYS: "日数",
  PURPOSE: "目的",
  PROJ: "案件コード",
  OVRSEA: "海外区分",
};

const KEY_LABELS: Record<string, string> = {
  F4: "案件コード選択",
  F9: "前回案件コード再利用",
  F3: "中断",
  Tab: "フィールド移動",
  FieldExit: "フィールド移動",
  Enter: "確定",
};

export function deriveIntent(step: Step): string {
  if (step.type === "field") {
    const label = (step.target && FIELD_LABELS[step.target]) || step.target || "項目";
    return `${label}入力`;
  }
  if (step.type === "nav") {
    return "画面遷移";
  }
  if (step.type === "fkey") {
    return (step.key && KEY_LABELS[step.key]) || step.key || "操作";
  }
  return "操作";
}
