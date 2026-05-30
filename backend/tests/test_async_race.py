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
from adapter.mock_adapter import MockAdapter
from backend import coreloop
from backend.coreloop import run_task
from backend.slotfill import RequestInput, Slots

MOCK_ROOT = Path(app_pkg.__file__).resolve().parent.parent
SLOTS = Slots(dest_code="OSAKA", purpose="製品X納入調整")


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


def _run(mock_client):
    adapter = MockAdapter(mock_client)
    adapter.open()
    return run_task(_request(), adapter, lambda request, context: SLOTS)


def test_async_race_login_apply(mock_client, monkeypatch):
    monkeypatch.setenv("MOCK_AS400_RENDER_DELAY_MS", "800")
    monkeypatch.setenv("MOCK_AS400_RENDER_JITTER_MS", "1200")
    outcome = _run(mock_client)
    assert outcome.status == "submitted"
    assert outcome.trip_id is not None


def test_async_race_zero_delay_control(mock_client):
    outcome = _run(mock_client)
    assert outcome.status == "submitted"
    assert outcome.trip_id is not None


def test_no_blind_sleep_in_execution_path():
    source = inspect.getsource(coreloop)
    assert "sleep" not in source
    assert "wait_for_timeout" not in source
