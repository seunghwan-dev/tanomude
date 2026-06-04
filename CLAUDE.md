# CLAUDE.md

Guardrails for autonomous and assisted work in this repository. Each rule exists because something went wrong without it — this file is the harness made explicit.

Tanomude is an on-premise AI assistant that operates AS-400-style legacy systems through natural-language instructions, human-in-the-loop approval, and per-user growth. It is run under the ringi-driven-harness methodology, and the design choices behind it are recorded as the numbered decision records at the end of this file.

## Git

- Do not `git commit` or `git push` unless the task explicitly authorizes it. State-changing git is the human's gate by default.
- Feature work goes on a branch and through a pull request. Never commit directly to `main`, except the initial bootstrap commit of a new repository.
- English commit messages. No AI co-author trailers or metadata. Never force-push or rewrite history without an explicit instruction.

## Files

- Write files as UTF-8 without a BOM. Never use PowerShell `>>` redirection to create or edit files — on Windows PowerShell it writes UTF-16 and corrupts UTF-8 files. Use the editor or Write tool.
- When a spec provides verbatim content, place it byte-for-byte. Blank lines are content; do not collapse them or add new ones.
- Do not delete a file unless the task names it.
- `_local/` is gitignored and local-only (master design, NDA material). Never commit its contents and never copy them into tracked files.

## Code

- No code comments in application source (Python / TypeScript). Code is self-documenting through clear names, type hints, and structured schemas; the "why" belongs in the Japanese master technical document, not inline. Application source only — comments in config, workflow YAML, and docs are intentional and must remain.
- Every LLM response must be enforced as structured output (JSON Schema / Pydantic) with retry. Free-form text where a schema is required is a defect.
- For asynchronous UI, never use `sleep()`. Assert with a Playwright wait-for-selector before the next action.

## Verification

- When reading or measuring a UTF-8 file in PowerShell, always pass `-Encoding UTF8`. The default encoding follows the system locale and will misread the file.
- When a measurement looks wrong, suspect the instrument before the artifact. Confirm with an encoding-independent method, such as a byte-level read, before reporting a defect.
- For byte-level checks under PowerShell 5.1, read raw bytes with `[System.IO.File]::ReadAllBytes(path)`. Do not use `Format-Hex -Count` — the `-Count` parameter is PowerShell 7+ only and errors on 5.1.

## Specs

- A task spec must be self-contained. A clean session sees only what is written. If intent is not written down, it does not exist — do not infer it.
- If a spec is ambiguous or contradicts what you observe, report it and ask. Do not guess, and do not blindly follow an instruction whose premise is false.

## Safety

- Never run `rm -rf`, `curl`, or pipe-to-shell installers.
- Never commit secrets. No `.env` files, keys, certificates, tokens, or credentials in tracked files. Secrets live in environment variables and GitHub Secrets only.
- Abstract confidential names to generic identifiers: company → `自社`, customer → `ABC商事`, product → `製品X`, equipment → `実験機A` / `実験機B`, material → `Material-X`.

## Reporting

- After a task, report what was created or changed, the verification results, and any deviation from the spec. If you departed from an instruction for a good reason, say so plainly.

## Implementer Principles

The habits expected of any agent building in this harness. The human gate is the last
line of defense — these keep less from ever reaching it.

1. **Think before coding.** Don't run with an unstated assumption. If a request is
   ambiguous, surface the interpretations and ask rather than guess. If a simpler path
   exists, say so. When confused, name what's unclear and stop — a paused build is
   cheaper than a wrong one.
2. **Simplicity first.** Write the minimum that solves the stated problem. No speculative
   abstractions, no configurability nobody asked for, no error handling for impossible
   cases. If it could be half the size, rewrite it. Test: would a senior engineer call
   this overcomplicated?
3. **Surgical changes.** Touch only what the task requires. Don't reformat, refactor, or
   "improve" adjacent code; match the existing style even if you'd do it differently.
   Remove only the orphans your own change created; leave pre-existing dead code alone
   unless asked. Test: every changed line traces to the request.
4. **Goal-driven execution.** Turn the task into a verifiable goal and loop until it's
   met. "Fix the bug" becomes "write a test that reproduces it, then make it pass." State
   a short plan with a check per step, then run to green.

**Bounded autonomy.** This harness runs on one rule: the AI proposes, the human decides.
Build, test, and prepare changes autonomously — but nothing reaches `main` without a
human's review and merge (the ringi stamp). Optimize for making that human decision easy
and well-informed, not for bypassing it.

## Decisions

Decision records for design choices made during tracked work in this repository.

- **[D-54]** The screen-adapter seam was extended to own its session lifecycle: `ScreenAdapter` gains
  `open(idempotency_key=None)` and `close()` as abstract methods alongside
  `read_screen`/`send_keys`/`assert_state`. `run_task` takes an unopened adapter and opens
  the session itself as its first action, deriving the idempotency key from
  `RequestInput.task_id` via `derive_idempotency_key` (`task:{task_id}`, `None` when there
  is no task id). This makes duplicate-submission defense active on the production
  core-loop path; the real AS-400 adapter will implement open/close as its connect/login
  and disconnect.

- **[D-55]** *(RETIRED — the four-way outcome clause below is superseded by [BL-01]; the
  承認済 seal-separation clause stated in this record remains in force.)* The frontend
  approval card separates the 承認済 seal from the execution
  outcome. The seal marks the approval act: it renders for every approved task regardless
  of how execution ends, and never renders while a task is awaiting approval. The execution
  result is surfaced independently as a four-way outcome on the timeline — submitted shows
  the trip id; a rolled-back execution flagged as bad data is surfaced as a growth candidate
  (育成候補) whose human correction is destined to become the next task's personal
  correction; a rolled-back execution that is not bad data (transient retries exhausted) is
  surfaced as needing investigation (要調査); a refused plan shows its reason. A
  non-submitted but approved outcome is no longer reported as a card-level error — the
  timeline outcome carries the result.

- **[BL-01]** Supersedes the four-way outcome clause of [D-55]. The timeline surfaces a
  four-way execution outcome: submitted shows the trip id; a rolled-back execution flagged as
  bad data is surfaced as 再入力/コード確認 — a passthrough input-validation failure (a
  malformed entered code the operator must check and re-enter), not a slot the model can be
  grown on; a rolled-back execution that is not bad data (transient retries exhausted) is
  surfaced as needing investigation (要調査); a refused plan shows its reason. 育成候補 is no
  longer an execution-outcome label — it is a static plan-view cue on the correction-movable
  inference slots {`overseas`, `reuse_prev_proj`} in the analysis view only. Engine routing is
  unchanged: bad data short-circuits replan (`replan_count = 0`) and is the human path, not a
  retry.
