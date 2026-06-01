import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

export type DecisionKind = "approve" | "revise" | "reject";

export default function ActionBar({
  onApprove,
  onRevise,
  onReject,
  pending,
  decided,
  error,
}: {
  onApprove: () => void;
  onRevise: (text: string) => void;
  onReject: (reason: string) => void;
  pending: DecisionKind | null;
  decided: "approved" | "rejected" | null;
  error: string | null;
}) {
  const [mode, setMode] = useState<"idle" | "revise" | "reject">("idle");
  const [reviseText, setReviseText] = useState("");
  const [rejectReason, setRejectReason] = useState("");

  const busy = pending !== null;
  const locked = decided !== null;
  const blocked = busy || locked;

  function toggle(next: "revise" | "reject") {
    if (blocked) {
      return;
    }
    setMode((current) => (current === next ? "idle" : next));
  }

  return (
    <div className="border-t border-line bg-paper-panel/80 px-5 py-4">
      <div className="flex items-center gap-3">
        <motion.button
          type="button"
          whileTap={{ scale: 0.96 }}
          disabled={blocked}
          onClick={onApprove}
          className="relative inline-flex items-center gap-2 rounded-lg bg-seal px-5 py-2.5 text-sm font-bold text-paper-panel shadow-seal transition-colors hover:bg-seal-deep disabled:opacity-50"
        >
          <span className="grid h-5 w-5 place-items-center rounded-full border-2 border-paper-panel/80 text-[10px] leading-none">
            印
          </span>
          {pending === "approve" ? "実行中…" : "承認"}
        </motion.button>

        <motion.button
          type="button"
          whileTap={{ scale: 0.96 }}
          disabled={blocked}
          onClick={() => toggle("revise")}
          className="rounded-lg border border-line bg-paper px-5 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-paper-sunk disabled:opacity-50"
        >
          修正
        </motion.button>

        <motion.button
          type="button"
          whileTap={{ scale: 0.96 }}
          disabled={blocked}
          onClick={() => toggle("reject")}
          className="rounded-lg px-4 py-2.5 text-sm font-medium text-ink-faint transition-colors hover:bg-paper-sunk hover:text-ink disabled:opacity-50"
        >
          却下
        </motion.button>

        <AnimatePresence>
          {decided === "approved" && !error ? (
            <motion.span
              key="stamp"
              initial={{ opacity: 0, scale: 0.6, rotate: -12 }}
              animate={{ opacity: 1, scale: 1, rotate: -8 }}
              className="ml-auto grid h-12 w-12 place-items-center rounded-full border-2 border-seal text-[10px] font-bold leading-tight text-seal"
            >
              承認
              <br />
              済
            </motion.span>
          ) : null}
          {decided === "rejected" ? (
            <motion.span
              key="rejected"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className="ml-auto rounded-full bg-seal-wash px-3 py-1.5 text-xs font-semibold text-seal-deep"
            >
              却下しました
            </motion.span>
          ) : null}
        </AnimatePresence>
      </div>

      {error ? <p className="mt-3 text-sm text-seal-deep">{error}</p> : null}

      <AnimatePresence initial={false}>
        {mode === "revise" && !locked ? (
          <motion.div
            key="revise"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="pt-4">
              <label className="mb-1.5 block text-xs font-semibold text-ink-soft">修正指示</label>
              <textarea
                value={reviseText}
                onChange={(e) => setReviseText(e.target.value)}
                rows={3}
                placeholder="例：目的地コードを KOBE に変更してください。"
                className="w-full resize-none rounded-lg border border-line bg-paper-panel px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-ink-soft focus:outline-none"
              />
              <div className="mt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  disabled={busy || reviseText.trim() === ""}
                  onClick={() => onRevise(reviseText.trim())}
                  className="rounded-md bg-ink px-3 py-1.5 text-sm font-semibold text-paper-panel transition-colors hover:bg-ink-soft disabled:opacity-50"
                >
                  {pending === "revise" ? "送信中…" : "修正を送信"}
                </button>
              </div>
            </div>
          </motion.div>
        ) : null}

        {mode === "reject" && !locked ? (
          <motion.div
            key="reject"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="pt-4">
              <label className="mb-1.5 block text-xs font-semibold text-ink-soft">却下理由（任意）</label>
              <input
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="理由を入力（省略可）"
                className="w-full rounded-lg border border-line bg-paper-panel px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-ink-soft focus:outline-none"
              />
              <div className="mt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onReject(rejectReason.trim())}
                  className="rounded-md bg-seal px-3 py-1.5 text-sm font-semibold text-paper-panel transition-colors hover:bg-seal-deep disabled:opacity-50"
                >
                  {pending === "reject" ? "確定中…" : "却下を確定"}
                </button>
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
