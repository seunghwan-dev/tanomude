import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

type Mode = "idle" | "approved" | "revise" | "reject";

const PENDING_NOTE = "（送信は次の実装で接続されます）";

export default function ActionBar() {
  const [mode, setMode] = useState<Mode>("idle");
  const [reviseText, setReviseText] = useState("");
  const [rejectReason, setRejectReason] = useState("");

  return (
    <div className="border-t border-line bg-paper-panel/80 px-5 py-4">
      <div className="flex items-center gap-3">
        <motion.button
          type="button"
          whileTap={{ scale: 0.96 }}
          onClick={() => setMode("approved")}
          className="relative inline-flex items-center gap-2 rounded-lg bg-seal px-5 py-2.5 text-sm font-bold text-paper-panel shadow-seal transition-colors hover:bg-seal-deep"
        >
          <span className="grid h-5 w-5 place-items-center rounded-full border-2 border-paper-panel/80 text-[10px] leading-none">
            印
          </span>
          承認
        </motion.button>

        <motion.button
          type="button"
          whileTap={{ scale: 0.96 }}
          onClick={() => setMode((m) => (m === "revise" ? "idle" : "revise"))}
          className="rounded-lg border border-line bg-paper px-5 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-paper-sunk"
        >
          修正
        </motion.button>

        <motion.button
          type="button"
          whileTap={{ scale: 0.96 }}
          onClick={() => setMode((m) => (m === "reject" ? "idle" : "reject"))}
          className="rounded-lg px-4 py-2.5 text-sm font-medium text-ink-faint transition-colors hover:bg-paper-sunk hover:text-ink"
        >
          却下
        </motion.button>

        <AnimatePresence>
          {mode === "approved" ? (
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
        </AnimatePresence>
      </div>

      <AnimatePresence initial={false}>
        {mode === "revise" ? (
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
                <span className="text-xs text-ink-faint">{PENDING_NOTE}</span>
                <button
                  type="button"
                  disabled
                  className="cursor-not-allowed rounded-md bg-paper-sunk px-3 py-1.5 text-sm font-medium text-ink-faint"
                >
                  修正を送信
                </button>
              </div>
            </div>
          </motion.div>
        ) : null}

        {mode === "reject" ? (
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
                <span className="text-xs text-ink-faint">{PENDING_NOTE}</span>
                <button
                  type="button"
                  disabled
                  className="cursor-not-allowed rounded-md bg-paper-sunk px-3 py-1.5 text-sm font-medium text-ink-faint"
                >
                  却下を確定
                </button>
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
