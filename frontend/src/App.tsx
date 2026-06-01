import { useState } from "react";

import { planTask, type TaskPlan } from "./api";
import ApprovalCard from "./components/ApprovalCard";

function TextField(props: { label: string; value: string; onChange: (value: string) => void; mono?: boolean }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold text-ink-soft">{props.label}</span>
      <input
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
        className={`w-full rounded-lg border border-line bg-paper-panel px-3 py-2 text-sm text-ink focus:border-ink-soft focus:outline-none ${
          props.mono ? "font-mono" : ""
        }`}
      />
    </label>
  );
}

export default function App() {
  const workflow = "shukko";
  const [instruction, setInstruction] = useState("製品Xの納入調整のため大阪へ出張する。");
  const [dest, setDest] = useState("大阪");
  const [deptDate, setDeptDate] = useState("2026-06-10");
  const [retDate, setRetDate] = useState("2026-06-11");
  const [projHint, setProjHint] = useState("P-001");
  const [result, setResult] = useState<TaskPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await planTask({
        workflow,
        instruction,
        fields: { dest, dept_date: deptDate, ret_date: retDate, proj_hint: projHint },
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "不明なエラーが発生しました");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-5 py-10">
      <header className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">
            tanomude<span className="text-seal">.</span>
          </h1>
          <p className="text-sm text-ink-faint">基幹系オペレーション 承認コンソール</p>
        </div>
        <div className="flex items-center gap-2 font-mono text-[11px] text-ink-faint">
          <span className="h-2 w-2 rounded-full bg-phosphor" />
          AS-400 / 出張申請
        </div>
      </header>

      <form onSubmit={onSubmit} className="mb-8 rounded-card border border-line bg-paper-panel p-5 shadow-card">
        <label className="mb-4 block">
          <span className="mb-1 block text-xs font-semibold text-ink-soft">指示</span>
          <textarea
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
            rows={2}
            className="w-full resize-none rounded-lg border border-line bg-paper-panel px-3 py-2 text-sm text-ink focus:border-ink-soft focus:outline-none"
          />
        </label>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <TextField label="出張先" value={dest} onChange={setDest} />
          <TextField label="出発日" value={deptDate} onChange={setDeptDate} mono />
          <TextField label="帰着日" value={retDate} onChange={setRetDate} mono />
          <TextField label="案件コード" value={projHint} onChange={setProjHint} mono />
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-ink px-5 py-2.5 text-sm font-semibold text-paper-panel transition-colors hover:bg-ink-soft disabled:opacity-50"
          >
            {loading ? "生成中…" : "計画を生成"}
          </button>
          {error ? <span className="text-sm text-seal-deep">{error}</span> : null}
        </div>
      </form>

      {result ? (
        <ApprovalCard result={result} />
      ) : (
        <div className="rounded-card border border-dashed border-line bg-paper-panel/50 px-5 py-16 text-center text-sm text-ink-faint">
          指示を入力し「計画を生成」を押すと、承認カードが表示されます。
        </div>
      )}
    </div>
  );
}
