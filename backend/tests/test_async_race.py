import inspect
from pathlib import Path

import app as app_pkg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db import SessionLocal as MockSessionLocal
from app.main import app as mock_app
from app.models import MockSession, TripApplication
from adapter.base import ScreenAdapter
from adapter.mock_adapter import MockAdapter
from backend import coreloop
from backend.coreloop import run_task
from backend.slotfill import RequestInput, Slots

MOCK_ROOT = Path(app_pkg.__file__).resolve().parent.parent
SLOTS = Slots(dest_code="OSAKA", purpose="製品X納入調整")

GUARANTEED_DELAY_MS = "800"
RENDER_JITTER_MS = "1200"


def _inject_guaranteed_delay(monkeypatch):
    monkeypatch.setenv("MOCK_AS400_RENDER_DELAY_MS", GUARANTEED_DELAY_MS)
    monkeypatch.setenv("MOCK_AS400_RENDER_JITTER_MS", RENDER_JITTER_MS)


class _ReadySpy(ScreenAdapter):
    def __init__(self, inner: ScreenAdapter):
        self._inner = inner
        self.ready_values: list[bool] = []

    def open(self, idempotency_key=None):
        return self._inner.open(idempotency_key)

    def close(self) -> None:
        self._inner.close()

    def read_screen(self):
        screen = self._inner.read_screen()
        self.ready_values.append(screen.ready)
        return screen

    def send_keys(self, step):
        screen = self._inner.send_keys(step)
        self.ready_values.append(screen.ready)
        return screen

    def assert_state(self, spec):
        return self._inner.assert_state(spec)

    def busy_observed(self) -> bool:
        return any(value is False for value in self.ready_values)


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


def _request() -> RequestInput:
    return RequestInput(
        workflow="shukko",
        instruction="出張申請",
        fields={"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11", "proj_hint": "P-001"},
    )


def _run(mock_client) -> tuple[coreloop.ExecutionOutcome, bool]:
    inner = MockAdapter(mock_client)
    spy = _ReadySpy(inner)
    outcome = run_task(_request(), spy, lambda request, context: SLOTS)
    return outcome, spy.busy_observed()


def test_async_race_login_apply(mock_client, monkeypatch):
    _inject_guaranteed_delay(monkeypatch)
    outcome, busy_observed = _run(mock_client)
    assert busy_observed is True
    assert outcome.status == "submitted"
    assert outcome.trip_id is not None


def test_async_race_zero_delay_control(mock_client):
    outcome, busy_observed = _run(mock_client)
    assert busy_observed is False
    assert outcome.status == "submitted"
    assert outcome.trip_id is not None


def test_no_blind_sleep_in_execution_path():
    source = inspect.getsource(coreloop)
    assert "sleep" not in source
    assert "wait_for_timeout" not in source
