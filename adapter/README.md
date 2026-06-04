# adapter — screen adapter seam

Clean seam between the agent and the operated system (AS-400 mock today, real AS-400 in
production). The `ScreenAdapter` ABC defines three primitives: `read_screen`, `send_keys`,
`assert_state`.

## Session lifecycle is outside the seam

`MockAdapter.open()` creates the mock session (`POST /session`) but is intentionally *not*
part of the `ScreenAdapter` ABC. Session lifecycle is implementation-specific — a real
AS-400 connect/login flow differs from the mock's session creation — so it is kept off the
seam, which stays focused on the read/send/assert verbs.

## Tests

The adapter tests are an in-process contract test: they import the `mock-as400` FastAPI app
and drive it via `TestClient`, and therefore require `mock-as400` to be installed in the same
environment (CI installs it before this step). They are not standalone-runnable.
