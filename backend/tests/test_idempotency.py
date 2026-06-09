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


@pytest.fixture(autouse=True)
def _no_render_delay(monkeypatch):
    monkeypatch.delenv("MOCK_AS400_RENDER_DELAY_MS", raising=False)
    monkeypatch.delenv("MOCK_AS400_RENDER_JITTER_MS", raising=False)


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


def _request(task_id: str | None) -> RequestInput:
    return RequestInput(
        workflow="shutchou",
        instruction="出張申請",
        fields={"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11", "proj_hint": "P-001"},
        task_id=task_id,
    )


def _run(mock_client, task_id):
    return run_task(_request(task_id), MockAdapter(mock_client), lambda request, context: SLOTS)


def test_same_task_id_submits_once(mock_client):
    before = _trip_count()
    first = _run(mock_client, "task-osaka-001")
    second = _run(mock_client, "task-osaka-001")
    assert first.status == "submitted"
    assert second.status == "submitted"
    assert _trip_count() == before + 1
    assert first.trip_id is not None
    assert second.trip_id == first.trip_id


def test_disabled_key_derivation_submits_twice(mock_client, monkeypatch):
    monkeypatch.setattr(coreloop, "derive_idempotency_key", lambda request: None)
    before = _trip_count()
    first = _run(mock_client, "task-osaka-001")
    second = _run(mock_client, "task-osaka-001")
    assert _trip_count() == before + 2
    assert first.trip_id is not None
    assert second.trip_id != first.trip_id


def test_duplicate_task_is_observable(mock_client):
    first = _run(mock_client, "task-observe")
    second = _run(mock_client, "task-observe")
    assert first.trip_created is True
    assert second.trip_created is False


def test_idempotent_under_render_delay(mock_client, monkeypatch):
    monkeypatch.setenv("MOCK_AS400_RENDER_DELAY_MS", "800")
    monkeypatch.setenv("MOCK_AS400_RENDER_JITTER_MS", "1200")
    before = _trip_count()
    first = _run(mock_client, "task-delay")
    second = _run(mock_client, "task-delay")
    assert first.status == "submitted"
    assert second.status == "submitted"
    assert _trip_count() == before + 1
    assert second.trip_id == first.trip_id
