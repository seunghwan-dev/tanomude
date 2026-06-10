import { useEffect, useLayoutEffect, useRef, useState } from "react";

import type { TaskStep } from "../api";
import {
  actionToCommand,
  FORM_FKEYS,
  type FormFieldSpec,
  MENU_FKEYS,
  MENU_OPTIONS,
  PROJ_LOOKUP,
  type ScreenTemplate,
  screenToTemplate,
  SYSTEM_BLOCK,
  TRIP_INPUT_FIELDS,
} from "../lib/screenRender";
import "./As400Screen.css";

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") {
      return undefined;
    }
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const onChange = () => setReduced(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

function Rule() {
  return (
    <div className="as400-line as400-rule" aria-hidden="true">
      {"─".repeat(72)}
    </div>
  );
}

function FormRow({ spec, value, active }: { spec: FormFieldSpec; value: string; active: boolean }) {
  return (
    <div className="as400-row">
      <span className="as400-lbl">{spec.label}</span>
      <span className="as400-lead" aria-hidden="true" />
      <span className="as400-sep">{`: ${spec.prompt ? ">" : " "}`}</span>
      <span
        className={spec.code ? "as400-field as400-code" : "as400-field"}
        style={{ minWidth: `${spec.width + (spec.code ? 2 : 0)}ch` }}
      >
        {spec.code ? "[" : ""}
        {value}
        {active ? <span className="as400-cursor" /> : null}
        {spec.code ? "]" : ""}
      </span>
      <span className="as400-hint">{spec.hint}</span>
    </div>
  );
}

function FkeyLegend({ keys, hotKey }: { keys: { key: string; label: string }[]; hotKey: string | null }) {
  return (
    <div className="as400-fkeys as400-line">
      {keys.map((fk) => (
        <span key={fk.key} className={fk.key === hotKey ? "as400-fkey as400-hot" : "as400-fkey"}>
          {`${fk.key}=${fk.label}`}
        </span>
      ))}
    </div>
  );
}

function StatusLine({ inhibit, counter }: { inhibit: boolean; counter: string }) {
  return (
    <div className="as400-statusln as400-line">
      <span>
        <span className={inhibit ? "as400-statusblock as400-on" : "as400-statusblock"} />
        {" MA*  A"}
      </span>
      <span>英数 半角</span>
      <span className="as400-spacer" />
      <span>{counter}</span>
    </div>
  );
}

function SystemBlock({ menu }: { menu: boolean }) {
  if (menu) {
    return <span className="as400-sysblock">{`システム . . : ${SYSTEM_BLOCK.system}`}</span>;
  }
  return (
    <span className="as400-sysblock">
      {`システム . . . : ${SYSTEM_BLOCK.system}\nサブシステム . : ${SYSTEM_BLOCK.subsystem}\n表示装置 . . . : ${SYSTEM_BLOCK.device}`}
    </span>
  );
}

function Header({ template, menu }: { template: ScreenTemplate; menu: boolean }) {
  return (
    <div className="as400-hdr">
      <span className="as400-ident">{template.code}</span>
      <span className="as400-title" style={{ flex: 1 }}>
        {template.title}
      </span>
      <SystemBlock menu={menu} />
    </div>
  );
}

function MenuBody({ template, flash }: { template: ScreenTemplate; flash: boolean }) {
  return (
    <>
      <Header template={template} menu />
      <Rule />
      <div className="as400-line"> </div>
      <div className="as400-line">{template.instruction}</div>
      <div className="as400-line"> </div>
      {MENU_OPTIONS.map((option) => (
        <div key={option.index} className="as400-line">
          {"    "}
          <span className={flash && option.active ? "as400-rev" : option.active ? "as400-hi" : "as400-dim"}>
            {`${option.index}. ${option.label}`}
          </span>
        </div>
      ))}
      <div className="as400-line"> </div>
      <div className="as400-line">
        {"    "}
        {"選択 ===> "}
        <span className="as400-field as400-code" style={{ minWidth: "3ch" }}>
          1
        </span>
      </div>
      <div className="as400-spacer" />
      <FkeyLegend keys={MENU_FKEYS} hotKey={null} />
      <StatusLine inhibit={false} counter="20/007" />
    </>
  );
}

function LookupWindow({ selected }: { selected: string }) {
  return (
    <div className="as400-lookup">
      <div className="as400-lookup-title">案件コード一覧</div>
      {PROJ_LOOKUP.map((entry, index) => {
        const chosen = selected ? entry.code === selected : index === 0;
        return (
          <div key={entry.code} className={chosen ? "as400-lookup-item as400-sel" : "as400-lookup-item"}>
            {`${entry.code}  ${entry.label}`}
          </div>
        );
      })}
    </div>
  );
}

function OutcomeBanner({ tripId }: { tripId: number | null }) {
  return (
    <div className="as400-outcome">
      {"登録完了    出張番号 "}
      <b>{tripId !== null ? `T-${tripId}` : "発番待ち"}</b>
      {"    "}
      <span className="as400-vchk">verify OK</span>
      {"    audit_log 記録済"}
    </div>
  );
}

export default function As400Screen({
  steps,
  cursor,
  tripId,
  fast,
}: {
  steps: TaskStep[];
  cursor: number;
  tripId: number | null;
  fast: boolean;
}) {
  const reduced = usePrefersReducedMotion();
  const current = steps[cursor] ?? null;
  const stepIdentity = current ? `${current.execution_id}:${current.ordinal}` : "idle";

  const [typed, setTyped] = useState("");
  const [hotKey, setHotKey] = useState<string | null>(null);
  const [navOrigin, setNavOrigin] = useState(false);
  const currentRef = useRef<TaskStep | null>(null);
  currentRef.current = current;
  const fastRef = useRef(fast);
  fastRef.current = fast;
  const timers = useRef<number[]>([]);

  useLayoutEffect(() => {
    for (const handle of timers.current) {
      window.clearTimeout(handle);
    }
    timers.current = [];
    setHotKey(null);
    setNavOrigin(false);

    const step = currentRef.current;
    if (!step) {
      setTyped("");
      return undefined;
    }

    const command = actionToCommand(step.action);
    const factor = fastRef.current ? 0.5 : 1;
    if (command.kind === "type") {
      const value = command.value;
      if (reduced) {
        setTyped(value);
      } else {
        setTyped("");
        const base = Math.max(14, Math.min(46, Math.floor(520 / Math.max(value.length, 1))));
        const perChar = Math.max(7, Math.round(base * factor));
        for (let index = 1; index <= value.length; index += 1) {
          timers.current.push(window.setTimeout(() => setTyped(value.slice(0, index)), perChar * index));
        }
      }
    } else if (command.kind === "key") {
      setTyped("");
      setHotKey(command.key);
      if (!reduced) {
        timers.current.push(window.setTimeout(() => setHotKey(null), Math.round(620 * factor)));
      }
    } else if (command.kind === "nav") {
      setTyped("");
      if (!reduced) {
        setNavOrigin(true);
        timers.current.push(window.setTimeout(() => setNavOrigin(false), Math.round(520 * factor)));
      }
    } else {
      setTyped("");
    }

    return () => {
      for (const handle of timers.current) {
        window.clearTimeout(handle);
      }
      timers.current = [];
    };
  }, [stepIdentity, reduced]);

  const command = current ? actionToCommand(current.action) : null;
  const template = current ? screenToTemplate(current.screen) : null;
  const fields = current?.screen_fields ?? {};
  const activeField = command && command.kind === "type" ? command.target : null;
  const menuTemplate = screenToTemplate("menu");

  const activeIndex = activeField ? TRIP_INPUT_FIELDS.findIndex((spec) => spec.key === activeField) : -1;
  const typedLength = activeField ? (reduced ? (fields[activeField] ?? "").length : typed.length) : 0;
  const counterRow = activeIndex >= 0 ? 6 + activeIndex : 5;
  const counterCol = activeIndex >= 0 ? 19 + typedLength : 7;
  const counter = `${String(counterRow).padStart(2, "0")}/${String(counterCol).padStart(3, "0")}`;

  function fieldValue(spec: FormFieldSpec): string {
    if (spec.key === activeField) {
      return reduced ? (fields[spec.key] ?? "") : typed;
    }
    return fields[spec.key] ?? "";
  }

  const showLookup = Boolean(current) && !navOrigin && template?.overlay === "lookup";
  const ariaLabel = current
    ? `AS-400 実行画面 ${current.screen ?? "—"}（ステップ ${current.ordinal}: ${current.intent}）`
    : "AS-400 実行画面（待機中）";

  let body: React.ReactNode;
  if (!current || !template) {
    body = <MenuBody template={menuTemplate} flash />;
  } else if (navOrigin || template.base === "menu") {
    body = <MenuBody template={menuTemplate} flash={navOrigin} />;
  } else if (template.base === "fallback") {
    body = (
      <>
        <Header template={template} menu={false} />
        <Rule />
        <div className="as400-line"> </div>
        <div className="as400-line as400-dim">{`画面 ${template.id}`}</div>
        {Object.entries(fields).map(([key, value]) => (
          <div key={key} className="as400-line">{`  ${key} . . : ${value}`}</div>
        ))}
        <div className="as400-spacer" />
        <FkeyLegend keys={FORM_FKEYS} hotKey={hotKey} />
        <StatusLine inhibit={hotKey !== null} counter={counter} />
      </>
    );
  } else {
    body = (
      <>
        <Header template={template} menu={false} />
        <Rule />
        <div className="as400-line">{template.instruction}</div>
        <div className="as400-line"> </div>
        <div className="as400-row">
          <span className="as400-lbl">申請者</span>
          <span className="as400-lead" aria-hidden="true" />
          <span className="as400-sep">{": "}</span>
          <span className="as400-dim">{SYSTEM_BLOCK.operator}</span>
        </div>
        {TRIP_INPUT_FIELDS.map((spec) => (
          <FormRow key={spec.key} spec={spec} value={fieldValue(spec)} active={spec.key === activeField} />
        ))}
        {template.overlay === "confirm" ? (
          <>
            <div className="as400-line"> </div>
            <div className="as400-line">確認: 実行キー(Enter)で申請を送信します。</div>
          </>
        ) : null}
        {template.overlay === "submitted" ? <OutcomeBanner tripId={tripId} /> : null}
        <div className="as400-spacer" />
        <FkeyLegend keys={FORM_FKEYS} hotKey={hotKey} />
        <StatusLine inhibit={hotKey !== null || template.overlay === "submitted"} counter={counter} />
      </>
    );
  }

  return (
    <div className="as400-root" aria-label={ariaLabel}>
      <div className="as400-screen">
        <div className="as400-body">{body}</div>
        {showLookup ? <LookupWindow selected={fields.PROJ ?? ""} /> : null}
      </div>
    </div>
  );
}
