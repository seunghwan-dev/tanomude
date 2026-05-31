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
from backend import embedding, ollama_client
from backend.coreloop import _attempt, execute, plan, run_task
from backend.ingest import ingest_manual, load_manual
from backend.slotfill import FilledKeysequence, Refusal, RequestInput, Slots, Step, extract_slots, fill, ground

MOCK_ROOT = Path(app_pkg.__file__).resolve().parent.parent


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


def _opened(mock_client) -> MockAdapter:
    adapter = MockAdapter(mock_client)
    adapter.open()
    return adapter


def _request(**field_overrides) -> RequestInput:
    fields = {"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11", "proj_hint": "P-001"}
    fields.update(field_overrides)
    return RequestInput(workflow="shukko", instruction="出張申請", fields=fields)


def _constant(slots: Slots):
    return lambda request, context: slots


SLOTS = Slots(dest_code="OSAKA", purpose="製品X納入調整")


def test_plan_produces_keysequence_without_adapter():
    result = plan(_request(), _constant(SLOTS))
    assert isinstance(result, FilledKeysequence)
    assert result.steps


def test_plan_refuses_on_missing_field_without_adapter():
    result = plan(_request(dest=""), _constant(SLOTS))
    assert isinstance(result, Refusal)
    assert result.missing_fields == ["DEST"]


def test_execute_opens_drives_and_submits(mock_client):
    filled = fill(_request(), _constant(SLOTS))
    outcome = execute(_request(), filled, MockAdapter(mock_client))
    assert outcome.status == "submitted"
    assert outcome.trip_id is not None


def test_valid_runs_to_submitted_and_creates_trip(mock_client):
    outcome = run_task(_request(), MockAdapter(mock_client), _constant(SLOTS))
    assert outcome.status == "submitted"
    assert outcome.trip_id is not None
    fetched = mock_client.get(f"/trip/{outcome.trip_id}")
    assert fetched.status_code == 200
    assert fetched.json()["dest"] == "OSAKA"
    assert fetched.json()["proj"] == "P-001"


def test_refusal_skips_execution_and_creates_no_trip(mock_client):
    before = _trip_count()
    called = []

    def slot_fn(request, context):
        called.append(1)
        return SLOTS

    outcome = run_task(_request(dest=""), MockAdapter(mock_client), slot_fn)
    assert outcome.status == "refused"
    assert outcome.refusal.missing_fields == ["DEST"]
    assert outcome.executed_steps == 0
    assert called == []
    assert _trip_count() == before


def test_verify_gate_halts_on_unfinished_sequence(mock_client):
    before = _trip_count()
    incomplete = FilledKeysequence(
        workflow="shukko",
        slots=SLOTS,
        steps=[
            Step(seq=1, type="nav", key="Enter"),
            Step(seq=2, type="field", target="DEST", value="OSAKA"),
        ],
    )
    outcome = _attempt(_opened(mock_client), incomplete)
    assert outcome.status == "verify_failed"
    assert outcome.final_screen != "submitted"
    assert _trip_count() == before


def test_verify_gate_halts_on_error_screen(mock_client):
    before = _trip_count()
    premature = FilledKeysequence(
        workflow="shukko",
        slots=SLOTS,
        steps=[
            Step(seq=1, type="nav", key="Enter"),
            Step(seq=2, type="fkey", key="Enter"),
        ],
    )
    outcome = _attempt(_opened(mock_client), premature)
    assert outcome.status == "verify_failed"
    assert outcome.errors
    assert _trip_count() == before


requires_models = pytest.mark.skipif(
    not (ollama_client.health() and embedding.health()),
    reason="ollama and/or embedding service not reachable",
)


@requires_models
def test_full_stack_smoke_reaches_submitted(mock_client, db):
    ingest_manual(db, workflow="shukko", title="出張申請 操作マニュアル",
                  source="shukko_manual.md", markdown=load_manual("shukko_manual.md"))
    request = _request()
    context = ground(db, request.instruction)
    outcome = run_task(request, MockAdapter(mock_client), extract_slots, context)
    assert outcome.status == "submitted"
    assert outcome.trip_id is not None
