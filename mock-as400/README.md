# mock-as400 — AS-400 stand-in

A deterministic green-screen state machine that stands in for the legacy AS-400 target, letting the agent's computer-use loop run without the real system. Behavior/state mock only — not the agent platform.

## Screen flow

`app/statemachine.py` drives a fixed set of screens: `login → menu → trip_input → confirm → submitted`. From `trip_input`, F4 opens `proj_prompt` and F9 recalls the previous project code; F3 aborts (`aborted`), and a failed Enter validation stays on `trip_input`. `submitted` and `aborted` are terminal.

## Layout

Three layers under `app/`:

- `routers/` — FastAPI endpoints: `/health`, `/session` (create · step · read), `/trip` (create · read).
- `services/` — `session_service` orchestrates the state machine and persistence (idempotent submit, optional render delay).
- `repositories/` — `session_repo` and `trip_repo` own all database access.

The app object is `app.main:app`. The `adapter/` contract tests import it and drive it in-process via FastAPI's `TestClient` (`adapter/tests/conftest.py`), so `mock-as400` must be installed alongside.

## Run and test

Built from this directory, the service serves on `:8400` (`docker compose up mock-as400`, with `mock-db`). Standalone:

```
pip install -e ".[dev]"
pytest
```
