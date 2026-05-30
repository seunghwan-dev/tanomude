from pathlib import Path

import app as app_pkg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import delete, func, select

from app.db import SessionLocal as MockSessionLocal
from app.main import app as mock_app
from app.models import MockSession, TripApplication
from adapter.mock_adapter import MockAdapter
from backend import ollama_client
from backend.coreloop import run_task
from backend.slotfill import MAX_PARSE_RETRY, SLOT_SYSTEM, RequestInput, SlotParseError, Slots, extract_slots

MOCK_ROOT = Path(app_pkg.__file__).resolve().parent.parent
VALID_TEXT = '{"dest_code":"OSAKA","purpose":"製品X納入調整","overseas":false,"reuse_prev_proj":false}'
NON_JSON = "this is not json"
WRONG_SHAPE = '{"unexpected":"shape"}'


def _text_source(script: list[str]):
    state = {"calls": 0}

    def source(system, prompt, **kwargs):
        index = min(state["calls"], len(script) - 1)
        state["calls"] += 1
        return script[index]

    return source, state


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


def test_transient_non_json_recovers_via_retry(mock_client, monkeypatch):
    source, state = _text_source([NON_JSON, VALID_TEXT])
    monkeypatch.setattr(ollama_client, "_generate_text", source)
    outcome = run_task(_request(), MockAdapter(mock_client), extract_slots)
    assert outcome.status == "submitted"
    assert outcome.trip_id is not None
    assert state["calls"] == 2
    assert _trip_count() == 1


def test_transient_schema_violation_recovers_via_retry(mock_client, monkeypatch):
    source, state = _text_source([WRONG_SHAPE, VALID_TEXT])
    monkeypatch.setattr(ollama_client, "_generate_text", source)
    outcome = run_task(_request(), MockAdapter(mock_client), extract_slots)
    assert outcome.status == "submitted"
    assert state["calls"] == 2
    assert _trip_count() == 1


def test_persistent_invalid_fails_safely(mock_client, monkeypatch):
    source, state = _text_source([NON_JSON])
    monkeypatch.setattr(ollama_client, "_generate_text", source)
    outcome = run_task(_request(), MockAdapter(mock_client), extract_slots)
    assert outcome.status == "parse_failed"
    assert outcome.errors
    assert outcome.trip_id is None
    assert state["calls"] == MAX_PARSE_RETRY + 1
    assert _trip_count() == 0


def test_retry_count_is_hard_capped(monkeypatch):
    source, state = _text_source([NON_JSON])
    monkeypatch.setattr(ollama_client, "_generate_text", source)
    with pytest.raises(SlotParseError) as excinfo:
        extract_slots(_request(), "")
    assert excinfo.value.retry_count == MAX_PARSE_RETRY
    assert len(excinfo.value.errors) == MAX_PARSE_RETRY + 1
    assert state["calls"] == MAX_PARSE_RETRY + 1


def test_without_retry_non_json_propagates(monkeypatch):
    monkeypatch.setattr(ollama_client, "_generate_text", lambda system, prompt, **kwargs: NON_JSON)
    with pytest.raises(ValueError):
        ollama_client.generate_json(SLOT_SYSTEM, "prompt")


def test_without_retry_schema_violation_propagates(monkeypatch):
    monkeypatch.setattr(ollama_client, "_generate_text", lambda system, prompt, **kwargs: WRONG_SHAPE)
    with pytest.raises(ValidationError):
        Slots(**ollama_client.generate_json(SLOT_SYSTEM, "prompt"))
