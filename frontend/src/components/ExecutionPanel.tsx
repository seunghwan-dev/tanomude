import type { Replay } from "../hooks/useReplay";
import Inspector from "./Inspector";
import Timeline from "./Timeline";

const STATUS_LABELS: Record<string, string> = {
  awaiting_approval: "承認待ち",
  running: "実行中",
  submitted: "送信済",
  rolled_back: "ロールバック",
  refused: "却下",
  failed: "失敗",
  errored: "エラー",
};

export default function ExecutionPanel({ replay }: { replay: Replay }) {
  const { steps, taskStatus, execution, connected, selected, activeKey, cursor, playing, play, stop, live, select } =
    replay;

  return (
    <section className="mt-6 overflow-hidden rounded-card border border-line bg-paper-panel shadow-card">
      <header className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-4">
        <div className="text-sm font-bold tracking-tight text-ink">実行タイムライン</div>
        <span className="flex items-center gap-1.5 font-mono text-[11px] text-ink-faint">
          <span className={`h-2 w-2 rounded-full ${connected ? "bg-phosphor" : "bg-ink-faint"}`} />
          {connected ? "LIVE" : "接続中…"}
        </span>
        <span className="rounded-full bg-paper-sunk px-3 py-1 text-xs font-semibold text-ink-soft">
          {STATUS_LABELS[taskStatus ?? ""] ?? taskStatus ?? "—"}
        </span>
        {execution?.finished ? (
          execution.tripId !== null ? (
            <span className="rounded-full bg-phosphor/10 px-3 py-1 font-mono text-xs font-semibold text-phosphor">
              trip #{execution.tripId}
            </span>
          ) : execution.badData ? (
            <span className="rounded-full bg-seal-wash px-3 py-1 text-xs font-semibold text-seal-deep">
              再入力/コード確認
            </span>
          ) : (
            <span className="rounded-full border border-line bg-paper px-3 py-1 text-xs font-semibold text-ink-soft">
              要調査
            </span>
          )
        ) : null}

        <div className="ml-auto flex items-center gap-1">
          {playing ? (
            <button
              type="button"
              onClick={stop}
              className="rounded-md border border-line bg-paper px-3 py-1.5 text-xs font-semibold text-ink hover:bg-paper-sunk"
            >
              停止
            </button>
          ) : (
            <button
              type="button"
              onClick={play}
              disabled={steps.length === 0}
              className="rounded-md border border-line bg-paper px-3 py-1.5 text-xs font-semibold text-ink hover:bg-paper-sunk disabled:opacity-40"
            >
              再生
            </button>
          )}
          <button
            type="button"
            onClick={live}
            disabled={steps.length === 0}
            className="rounded-md px-3 py-1.5 text-xs font-medium text-ink-faint hover:bg-paper-sunk hover:text-ink disabled:opacity-40"
          >
            ライブ
          </button>
          <span className="ml-1 font-mono text-[11px] text-ink-faint">
            {steps.length === 0 ? "0/0" : `${cursor + 1}/${steps.length}`}
          </span>
        </div>
      </header>

      {execution?.finished && execution.tripId === null ? (
        <div
          className={
            execution.badData
              ? "border-b border-line bg-seal-wash/40 px-5 py-3"
              : "border-b border-line bg-paper-sunk px-5 py-3"
          }
        >
          {execution.badData ? (
            <p className="text-sm text-seal-deep">
              <span className="font-semibold">再入力/コード確認：</span>
              入力されたコードが基幹システムの検証を通らず、差し戻されました。案件コード等の入力値をご確認のうえ、修正して再入力してください。
            </p>
          ) : (
            <p className="text-sm text-ink-soft">
              <span className="font-semibold">要調査：</span>
              再試行を尽くしても画面状態が整合せず差し戻されました。データの誤りではなく、一時的・実行環境側の事象として調査が必要です。
            </p>
          )}
        </div>
      ) : null}

      <div className="grid gap-4 p-5 md:grid-cols-12">
        <div className="max-h-[24rem] overflow-y-auto md:col-span-5">
          <Timeline steps={steps} activeKey={activeKey} onSelect={select} />
        </div>
        <div className="rounded-lg border border-line/70 bg-paper p-4 md:col-span-7">
          <Inspector step={selected} />
        </div>
      </div>
    </section>
  );
}
