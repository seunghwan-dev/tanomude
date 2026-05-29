import json
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
from backend.coreloop import run_task
from backend.ingest import ingest_manual, load_manual
from backend.slotfill import RequestInput, extract_slots, ground

CASES = json.loads((Path(__file__).resolve().parent / "fixtures" / "cases.json").read_text(encoding="utf-8"))["cases"]
MOCK_ROOT = Path(app_pkg.__file__).resolve().parent.parent

requires_models = pytest.mark.skipif(
    not (ollama_client.health() and embedding.health()),
    reason="ollama and/or embedding service not reachable",
)


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


@requires_models
@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_w1_capstone_full_stack(case, mock_client, db):
    adapter = MockAdapter(mock_client)
    adapter.open()
    request = RequestInput(workflow="shukko", instruction=case["input"]["instruction"], fields=case["input"]["fields"])
    cid = case["case_id"]

    if cid == "case_04_edge_empty_required":
        before = _trip_count()
        outcome = run_task(request, adapter, extract_slots)
        assert outcome.status == "refused"
        assert outcome.executed_steps == 0
        assert _trip_count() == before
        return

    ingest_manual(db, workflow="shukko", title="出張申請 操作マニュアル",
                  source="shukko_manual.md", markdown=load_manual("shukko_manual.md"))
    context = ground(db, request.instruction)
    outcome = run_task(request, adapter, extract_slots, context)
    assert outcome.status == "submitted"
    assert outcome.trip_id is not None

    if cid == "case_07_edge_reuse_prev":
        assert outcome.executed_steps == 11

    trip = mock_client.get(f"/trip/{outcome.trip_id}").json()
    if cid == "case_03_edge_branch_overseas":
        assert trip["overseas"] is True
    if cid == "case_05_edge_invalid_proj":
        assert trip["proj"] == "P-002"
    if cid == "case_06_edge_long_purpose":
        assert len(trip["purpose"]) <= 20
    if cid == "case_07_edge_reuse_prev":
        assert trip["proj"] == "P-002"
    if cid == "case_08_edge_days_recalc":
        assert trip["days"] == 4
