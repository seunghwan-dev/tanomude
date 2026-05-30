import hashlib
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


def _request() -> RequestInput:
    return RequestInput(
        workflow="shukko",
        instruction="出張申請",
        fields={"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11", "proj_hint": "P-001"},
    )


def _key(request: RequestInput) -> str:
    raw = repr([request.workflow, sorted(request.fields.items())])
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _run(mock_client, key):
    adapter = MockAdapter(mock_client)
    adapter.open(idempotency_key=key)
    return run_task(_request(), adapter, lambda request, context: SLOTS)


def test_same_task_submits_once(mock_client):
    key = _key(_request())
    before = _trip_count()
    first = _run(mock_client, key)
    second = _run(mock_client, key)
    assert first.status == "submitted"
    assert second.status == "submitted"
    assert _trip_count() == before + 1
    assert first.trip_id is not None
    assert second.trip_id == first.trip_id


def test_missing_key_submits_twice(mock_client):
    before = _trip_count()
    first = _run(mock_client, None)
    second = _run(mock_client, None)
    assert _trip_count() == before + 2
    assert first.trip_id is not None
    assert second.trip_id != first.trip_id


def test_duplicate_submission_is_observable(mock_client):
    key = _key(_request())
    first = _run(mock_client, key)
    second = _run(mock_client, key)
    assert first.trip_created is True
    assert second.trip_created is False
