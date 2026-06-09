from backend.agent import service
from backend.coreloop import ExecutionOutcome
from backend.slotfill import RequestInput


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _request() -> RequestInput:
    return RequestInput(
        workflow="shutchou",
        instruction="出張申請",
        fields={"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11", "proj_hint": "P-001"},
    )


def test_production_runner_grounds_and_threads_context(monkeypatch):
    captured: dict = {}

    def fake_ground(db, query):
        captured["query"] = query
        return "GROUNDED-CONTEXT"

    def fake_run_task(request, adapter, slot_fn, context="", observer=None):
        captured["context"] = context
        return ExecutionOutcome(status="submitted", executed_steps=1)

    monkeypatch.setattr(service, "SessionLocal", _FakeSession)
    monkeypatch.setattr(service, "ground", fake_ground)
    monkeypatch.setattr(service, "run_task", fake_run_task)

    outcome = service._production_runner(_request())

    assert outcome.status == "submitted"
    assert captured["query"] == "出張申請"
    assert captured["context"] == "GROUNDED-CONTEXT"
