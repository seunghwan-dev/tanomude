import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import TripApplication
from adapter.mock_adapter import MockAdapter
from adapter.types import KeyStep

FLOW = [
    KeyStep(type="nav", key="Enter"),
    KeyStep(type="nav", key="Enter"),
    KeyStep(type="field", target="DEST", value="OSAKA"),
    KeyStep(type="field", target="DEPTDATE", value="20260610"),
    KeyStep(type="field", target="RETDATE", value="20260611"),
    KeyStep(type="field", target="DAYS", value="2"),
    KeyStep(type="field", target="PURPOSE", value="製品X納入調整"),
    KeyStep(type="fkey", key="F4"),
    KeyStep(type="field", target="PROJ", value="P-001"),
    KeyStep(type="fkey", key="Enter"),
    KeyStep(type="fkey", key="Enter"),
]


@pytest.fixture(autouse=True)
def _no_render_delay(monkeypatch):
    monkeypatch.delenv("MOCK_AS400_RENDER_DELAY_MS", raising=False)
    monkeypatch.delenv("MOCK_AS400_RENDER_JITTER_MS", raising=False)


def _trip_count() -> int:
    with SessionLocal() as session:
        return session.scalar(select(func.count()).select_from(TripApplication))


def _submit(client, key):
    adapter = MockAdapter(client)
    adapter.open(idempotency_key=key)
    screen = None
    for step in FLOW:
        screen = adapter.send_keys(step)
    return screen


def test_same_key_submits_once(mock_client):
    before = _trip_count()
    first = _submit(mock_client, "task-osaka-20260610")
    second = _submit(mock_client, "task-osaka-20260610")
    assert first.screen == "submitted"
    assert second.screen == "submitted"
    assert _trip_count() == before + 1
    assert first.trip_id is not None
    assert second.trip_id == first.trip_id


def test_missing_key_submits_twice(mock_client):
    before = _trip_count()
    first = _submit(mock_client, None)
    second = _submit(mock_client, None)
    assert _trip_count() == before + 2
    assert first.trip_id is not None
    assert second.trip_id != first.trip_id


def test_duplicate_submission_is_observable(mock_client):
    first = _submit(mock_client, "task-key-observe")
    second = _submit(mock_client, "task-key-observe")
    assert first.trip_created is True
    assert second.trip_created is False
