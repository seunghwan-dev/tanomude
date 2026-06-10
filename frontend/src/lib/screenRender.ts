export type FieldKey = "DEST" | "DEPTDATE" | "RETDATE" | "DAYS" | "PURPOSE" | "OVRSEA" | "PROJ";

export interface FormFieldSpec {
  key: FieldKey;
  label: string;
  width: number;
  code: boolean;
  prompt: boolean;
  hint: string;
}

export interface MenuOption {
  index: number;
  label: string;
  active: boolean;
}

export interface FunctionKey {
  key: string;
  label: string;
}

export interface LookupEntry {
  code: string;
  label: string;
}

export type ScreenBase = "menu" | "form" | "fallback";
export type ScreenOverlay = "none" | "lookup" | "confirm" | "submitted";

export interface ScreenTemplate {
  id: string;
  base: ScreenBase;
  overlay: ScreenOverlay;
  code: string;
  title: string;
  instruction: string;
}

export type Command =
  | { kind: "type"; target: string | null; value: string }
  | { kind: "key"; key: string | null }
  | { kind: "nav"; target: string | null }
  | { kind: "noop" };

interface ActionLike {
  type: string;
  target?: string | null;
  value?: string | null;
  key?: string | null;
}

export const SYSTEM_BLOCK = {
  system: "TANOMU",
  subsystem: "TNMINT",
  device: "TNMDSP1",
  operator: "OPERATOR",
};

export const TRIP_INPUT_FIELDS: FormFieldSpec[] = [
  { key: "DEST", label: "目的地コード", width: 12, code: true, prompt: true, hint: "都市コード" },
  { key: "DEPTDATE", label: "出発日", width: 8, code: false, prompt: false, hint: "YYYYMMDD" },
  { key: "RETDATE", label: "帰着日", width: 8, code: false, prompt: false, hint: "YYYYMMDD" },
  { key: "DAYS", label: "日数", width: 3, code: false, prompt: false, hint: "数値" },
  { key: "PURPOSE", label: "目的", width: 20, code: false, prompt: false, hint: "20桁以内" },
  { key: "OVRSEA", label: "海外区分", width: 1, code: false, prompt: false, hint: "Y/N" },
  { key: "PROJ", label: "案件コード", width: 5, code: true, prompt: true, hint: "P-### F4" },
];

export const MENU_OPTIONS: MenuOption[] = [
  { index: 1, label: "出張申請", active: true },
  { index: 2, label: "出張精算", active: false },
  { index: 3, label: "出張報告書", active: false },
  { index: 4, label: "ログオフ", active: false },
];

export const FORM_FKEYS: FunctionKey[] = [
  { key: "F3", label: "中断" },
  { key: "F4", label: "案件コード選択" },
  { key: "F9", label: "前回案件コード再利用" },
  { key: "Enter", label: "確定" },
];

export const MENU_FKEYS: FunctionKey[] = [
  { key: "F3", label: "終了" },
  { key: "Enter", label: "選択" },
];

export const PROJ_LOOKUP: LookupEntry[] = [
  { code: "P-001", label: "製品X 案件" },
  { code: "P-002", label: "実験機A 案件" },
  { code: "P-003", label: "海外商談 案件" },
];

const FORM_TITLE = "出張申請  (TRAVEL REQUEST)";
const FORM_CODE = "ZTRVL01";
const FORM_INSTRUCTION = "選択項目を入力して、実行キーを押してください。";

const TEMPLATES: Record<string, ScreenTemplate> = {
  menu: {
    id: "menu",
    base: "menu",
    overlay: "none",
    code: "MENU01",
    title: "業務メニュー",
    instruction: "次の 1 つを選択してください。",
  },
  trip_input: {
    id: "trip_input",
    base: "form",
    overlay: "none",
    code: FORM_CODE,
    title: FORM_TITLE,
    instruction: FORM_INSTRUCTION,
  },
  proj_prompt: {
    id: "proj_prompt",
    base: "form",
    overlay: "lookup",
    code: FORM_CODE,
    title: FORM_TITLE,
    instruction: FORM_INSTRUCTION,
  },
  confirm: {
    id: "confirm",
    base: "form",
    overlay: "confirm",
    code: FORM_CODE,
    title: FORM_TITLE,
    instruction: "実行キーで申請を送信してください。",
  },
  submitted: {
    id: "submitted",
    base: "form",
    overlay: "submitted",
    code: FORM_CODE,
    title: FORM_TITLE,
    instruction: FORM_INSTRUCTION,
  },
};

const FALLBACK_TEMPLATE: ScreenTemplate = {
  id: "unknown",
  base: "fallback",
  overlay: "none",
  code: "------",
  title: "（未定義画面）",
  instruction: "",
};

export function screenToTemplate(screenId: string | null): ScreenTemplate {
  const template = TEMPLATES[screenId ?? ""];
  if (!template) {
    return { ...FALLBACK_TEMPLATE, id: screenId ?? "unknown" };
  }
  return template;
}

export function actionToCommand(action: ActionLike): Command {
  if (action.type === "field") {
    return { kind: "type", target: action.target ?? null, value: action.value ?? "" };
  }
  if (action.type === "fkey") {
    return { kind: "key", key: action.key ?? null };
  }
  if (action.type === "nav") {
    return { kind: "nav", target: action.target ?? null };
  }
  return { kind: "noop" };
}
