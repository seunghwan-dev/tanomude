import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend.agent.app import app
from backend.agent.service import get_plan_runner, get_runner
from backend.coreloop import ExecutionOutcome
from backend.db import SessionLocal
from backend.models import Approval, AuditLog, Execution, Plan, Task
from backend.retrieval import RetrievedChunk
from backend.slotfill import FilledKeysequence, Slots, Step

SUBMITTED = ExecutionOutcome(
    status="submitted", trip_id=42, trip_created=True, executed_steps=11, final_screen="submitted"
)
SLOTS = Slots(dest_code="OSAKA", purpose="製品X納入調整")
STEPS = [
    Step(seq=1, type="nav", key="Enter"),
    Step(seq=2, type="field", target="DEST", value="OSAKA"),
]
FILLED = FilledKeysequence(workflow="shukko", steps=STEPS, slots=SLOTS)
GROUNDS = [
    RetrievedChunk(chunk_id=3, doc_id=1, section="apply", heading="申請手順", text="F4で案件を選ぶ", score=0.42, rank=1)
]


@pytest.fixture
def client():
    test_client = TestClient(app)
    app.dependency_overrides[get_runner] = lambda: (lambda request, observer=None: SUBMITTED)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()
        with SessionLocal() as session:
            session.execute(delete(AuditLog))
            session.execute(delete(Approval))
            session.execute(delete(Plan))
            session.execute(delete(Execution))
            session.execute(delete(Task))
            session.commit()


def _counts() -> tuple[int, int]:
    with SessionLocal() as session:
        tasks = session.scalar(select(func.count()).select_from(Task))
        executions = session.scalar(select(func.count()).select_from(Execution))
    return tasks, executions


def _body(**overrides) -> dict:
    payload = {"workflow": "shukko", "instruction": "出張申請", "fields": {"dest": "大阪"}, "dedup_key": "task:dup"}
    payload.update(overrides)
    return payload


def test_duplicate_create_returns_409_with_existing_task(client):
    first = client.post("/tasks", json=_body())
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["status"] == "submitted"
    trip_id = first_body["executions"][0]["trip_id"]

    second = client.post("/tasks", json=_body())
    assert second.status_code == 409
    second_body = second.json()
    assert second_body["id"] == first_body["id"]
    assert second_body["executions"][0]["trip_id"] == trip_id
    assert _counts() == (1, 1)


def test_distinct_dedup_keys_both_create_without_conflict(client):
    first = client.post("/tasks", json=_body(dedup_key="task:a"))
    second = client.post("/tasks", json=_body(dedup_key="task:b"))
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert _counts() == (2, 2)


def test_duplicate_plan_returns_409_with_existing_task_and_plan(client):
    app.dependency_overrides[get_plan_runner] = lambda: (lambda request: (FILLED, GROUNDS))
    first = client.post("/tasks/plan", json=_body(dedup_key="task:plan:dup"))
    assert first.status_code == 201
    first_body = first.json()
    first_task_id = first_body["task"]["id"]
    first_plan_id = first_body["plan"]["id"]

    second = client.post("/tasks/plan", json=_body(dedup_key="task:plan:dup"))
    assert second.status_code == 409
    second_body = second.json()
    assert second_body["task"]["id"] == first_task_id
    assert second_body["plan"] is not None
    assert second_body["plan"]["id"] == first_plan_id
    assert second_body["plan"]["analysis"]["dest_code"] == "OSAKA"
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 1
        assert session.scalar(select(func.count()).select_from(Plan)) == 1
