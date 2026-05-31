from pathlib import Path

import app as app_pkg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db import SessionLocal as MockSessionLocal
from app.main import app as mock_app
from app.models import MockSession, TripApplication
from adapter.base import ScreenAdapter
from adapter.mock_adapter import MockAdapter
from backend import coreloop
from backend.coreloop import MAX_REPLAN, _attempt, derive_idempotency_key, run_task
from backend.slotfill import RequestInput, Slots, fill

MOCK_ROOT = Path(app_pkg.__file__).resolve().parent.parent
SLOTS = Slots(dest_code="OSAKA", purpose="製品X納入調整")


class _ConfirmStuckSpy(ScreenAdapter):
    def __init__(self, inner: ScreenAdapter, fail_submits: int):
        self._inner = inner
        self._fail_submits = fail_submits
        self.swallowed = 0
        self.f3_sent = 0

    def open(self, idempotency_key=None):
        return self._inner.open(idempotency_key)

    def close(self) -> None:
        self._inner.close()

    def read_screen(self):
        return self._inner.read_screen()

    def send_keys(self, step):
        if step.key == "F3":
            self.f3_sent += 1
        if step.key == "Enter" and self.swallowed < self._fail_submits:
            current = self._inner.read_screen()
            if current.screen == "confirm":
                self.swallowed += 1
                return current
        return self._inner.send_keys(step)

    def assert_state(self, spec):
        return self._inner.assert_state(spec)


@pytest.fixture(scope="module", autouse=True)
def mock_schema():
    config = Config(str(MOCK_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(MOCK_ROOT / "alembic"))
    command.upgrade(config, "head")
    yield


@pytest.fixture
def mock_client():
    client = TestClient(mock_app)
    try:
        yield client
    finally:
        with MockSessionLocal() as session:
            session.execute(delete(MockSession))
            session.execute(delete(TripApplication))
            session.commit()


def _trip_count() -> int:
    with MockSessionLocal() as session:
        return session.scalar(select(func.count()).select_from(TripApplication))


def _request() -> RequestInput:
    return RequestInput(
        workflow="shukko",
        instruction="出張申請",
        fields={"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11", "proj_hint": "P-001"},
    )


def _constant(slots: Slots):
    return lambda request, context: slots


def test_transient_mismatch_recovers_via_replan(mock_client):
    spy = _ConfirmStuckSpy(MockAdapter(mock_client), fail_submits=1)
    outcome = run_task(_request(), spy, _constant(SLOTS))
    assert outcome.status == "submitted"
    assert outcome.trip_id is not None
    assert outcome.correction_candidate is None
    assert spy.swallowed == 1
    assert spy.f3_sent == 1
    assert _trip_count() == 1


def test_persistent_mismatch_rolls_back_with_correction_candidate(mock_client):
    spy = _ConfirmStuckSpy(MockAdapter(mock_client), fail_submits=99)
    outcome = run_task(_request(), spy, _constant(SLOTS))
    assert outcome.status == "rolled_back"
    assert outcome.final_screen == "aborted"
    assert outcome.trip_id is None
    candidate = outcome.correction_candidate
    assert candidate is not None
    assert candidate.expected == "submitted"
    assert candidate.screen == "confirm"
    assert candidate.diffs
    assert candidate.replan_count == MAX_REPLAN
    assert _trip_count() == 0


def test_replan_count_is_hard_capped(mock_client):
    spy = _ConfirmStuckSpy(MockAdapter(mock_client), fail_submits=99)
    outcome = run_task(_request(), spy, _constant(SLOTS))
    assert outcome.status == "rolled_back"
    assert outcome.correction_candidate.replan_count == MAX_REPLAN
    assert spy.swallowed == MAX_REPLAN + 1


def test_rollback_reaches_aborted_independent_of_max_replan(mock_client, monkeypatch):
    monkeypatch.setattr(coreloop, "MAX_REPLAN", 0)
    spy = _ConfirmStuckSpy(MockAdapter(mock_client), fail_submits=99)
    outcome = run_task(_request(), spy, _constant(SLOTS))
    assert outcome.status == "rolled_back"
    assert outcome.final_screen == "aborted"
    assert outcome.correction_candidate.replan_count == 0
    assert _trip_count() == 0


def test_without_replan_persistent_mismatch_is_verify_failed(mock_client):
    spy = _ConfirmStuckSpy(MockAdapter(mock_client), fail_submits=99)
    spy.open(derive_idempotency_key(_request()))
    filled = fill(_request(), _constant(SLOTS))
    outcome = _attempt(spy, filled)
    spy.close()
    assert outcome.status == "verify_failed"
    assert outcome.final_screen == "confirm"
    assert spy.f3_sent == 0
    assert _trip_count() == 0
