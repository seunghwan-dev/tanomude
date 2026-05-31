import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend.agent.app import app
from backend.agent.manager import manager
from backend.agent.service import get_execute_runner, get_plan_runner
from backend.coreloop import ExecutionOutcome
from backend.db import SessionLocal
from backend.models import Approval, AuditLog, Execution, Plan, Task
from backend.retrieval import RetrievedChunk
from backend.slotfill import FilledKeysequence, Slots, Step

SLOTS = Slots(dest_code="OSAKA", purpose="製品X納入調整")
STEPS = [
    Step(seq=1, type="nav", key="Enter"),
    Step(seq=2, type="field", target="DEST", value="OSAKA"),
]
FILLED = FilledKeysequence(workflow="shukko", steps=STEPS, slots=SLOTS)
GROUNDS = [
    RetrievedChunk(chunk_id=3, doc_id=1, section="apply", heading="申請手順", text="F4で案件を選ぶ", score=0.42, rank=1)
]
SUBMITTED = ExecutionOutcome(
    status="submitted", trip_id=42, trip_created=True, executed_steps=11, final_screen="submitted"
)


@pytest.fixture
def client():
    test_client = TestClient(app)
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


def _seed_awaiting(client) -> int:
    app.dependency_overrides[get_plan_runner] = lambda: (lambda request: (FILLED, GROUNDS))
    body = {"workflow": "shukko", "instruction": "出張申請", "fields": {"dest": "大阪"}, "dedup_key": "task:dec:1"}
    return client.post("/tasks/plan", json=body).json()["task"]["id"]


def _use_execute_runner(outcome: ExecutionOutcome) -> None:
    app.dependency_overrides[get_execute_runner] = lambda: (lambda request, filled: outcome)


def test_approve_records_decision_and_executes(client):
    task_id = _seed_awaiting(client)
    _use_execute_runner(SUBMITTED)
    response = client.post(f"/tasks/{task_id}/approve", json={"approver": "tanaka"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "submitted"
    assert body["executions"][0]["status"] == "submitted"
    assert body["executions"][0]["trip_id"] == 42
    with SessionLocal() as session:
        approval = session.scalars(select(Approval).where(Approval.task_id == task_id)).one()
        assert approval.decision == "approve"
        assert approval.plan_id is not None
        audit = session.scalars(select(AuditLog).where(AuditLog.task_id == task_id)).one()
        assert audit.decision == "approve"
        assert session.get(Task, task_id).status == "submitted"


def test_approve_broadcasts_approved_then_execution_events(client):
    task_id = _seed_awaiting(client)
    _use_execute_runner(SUBMITTED)
    with client.websocket_connect("/ws/agent") as ws:
        client.post(f"/tasks/{task_id}/approve", json={"approver": "tanaka"})
        events = [ws.receive_json() for _ in range(4)]
    assert [event["type"] for event in events] == [
        "approved",
        "execution_started",
        "execution_finished",
        "status_changed",
    ]
    assert events[0]["payload"]["status"] == "running"
    assert events[3]["payload"]["status"] == "submitted"


def test_approve_execute_exception_marks_errored_not_orphan(client):
    task_id = _seed_awaiting(client)

    def _raising(request, filled):
        raise RuntimeError("boom")

    app.dependency_overrides[get_execute_runner] = lambda: _raising
    with pytest.raises(RuntimeError):
        client.post(f"/tasks/{task_id}/approve", json={"approver": "tanaka"})
    with SessionLocal() as session:
        task = session.get(Task, task_id)
        assert task.status == "failed"
        execution = session.scalars(select(Execution).where(Execution.task_id == task_id)).one()
        assert execution.status == "errored"
        assert execution.finished_at is not None


def test_reject_records_correction_and_refuses_without_executing(client):
    task_id = _seed_awaiting(client)
    response = client.post(
        f"/tasks/{task_id}/reject", json={"approver": "tanaka", "decision_text": "案件コード誤り"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "refused"
    with SessionLocal() as session:
        approval = session.scalars(select(Approval).where(Approval.task_id == task_id)).one()
        assert approval.decision == "reject"
        assert approval.decision_text == "案件コード誤り"
        audit = session.scalars(select(AuditLog).where(AuditLog.task_id == task_id)).one()
        assert audit.decision == "reject"
        assert session.get(Task, task_id).status == "refused"
        assert session.scalar(
            select(func.count()).select_from(Execution).where(Execution.task_id == task_id)
        ) == 0


def test_revise_records_approval_row_keeps_awaiting_and_no_new_plan(client):
    task_id = _seed_awaiting(client)
    with SessionLocal() as session:
        plans_before = session.scalar(
            select(func.count()).select_from(Plan).where(Plan.task_id == task_id)
        )
    response = client.post(
        f"/tasks/{task_id}/revise", json={"approver": "tanaka", "decision_text": "目的を具体化して"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_approval"
    with SessionLocal() as session:
        approval = session.scalars(select(Approval).where(Approval.task_id == task_id)).one()
        assert approval.decision == "revise"
        assert approval.decision_text == "目的を具体化して"
        audit = session.scalars(
            select(AuditLog).where(AuditLog.task_id == task_id, AuditLog.decision == "revise")
        ).one()
        assert audit.decision == "revise"
        assert session.get(Task, task_id).status == "awaiting_approval"
        plans_after = session.scalar(
            select(func.count()).select_from(Plan).where(Plan.task_id == task_id)
        )
    assert plans_after == plans_before


@pytest.mark.parametrize("action", ["approve", "reject", "revise"])
def test_decision_conflicts_when_not_awaiting(client, action):
    task_id = _seed_awaiting(client)
    with SessionLocal() as session:
        session.get(Task, task_id).status = "running"
        session.commit()
    response = client.post(
        f"/tasks/{task_id}/{action}", json={"approver": "tanaka", "decision_text": "x"}
    )
    assert response.status_code == 409
    with SessionLocal() as session:
        assert session.get(Task, task_id).status == "running"
        assert session.scalar(
            select(func.count()).select_from(Approval).where(Approval.task_id == task_id)
        ) == 0


def test_decision_404_for_missing_task(client):
    assert client.post("/tasks/999999/approve", json={"approver": "tanaka"}).status_code == 404


def test_reject_commit_precedes_broadcast(client, monkeypatch):
    task_id = _seed_awaiting(client)
    observations: list[str] = []
    original = manager.broadcast

    async def spy(event_type, tid, payload):
        if event_type == "rejected":
            with SessionLocal() as session:
                observations.append(session.get(Task, tid).status)
        await original(event_type, tid, payload)

    monkeypatch.setattr(manager, "broadcast", spy)
    client.post(f"/tasks/{task_id}/reject", json={"approver": "tanaka", "decision_text": "x"})
    assert observations == ["refused"]


def test_get_after_decision_is_read_only(client):
    task_id = _seed_awaiting(client)
    client.post(f"/tasks/{task_id}/revise", json={"approver": "tanaka", "decision_text": "x"})
    with SessionLocal() as session:
        before_updated = session.get(Task, task_id).updated_at
        before = session.scalar(select(func.count()).select_from(Approval))

    client.get(f"/tasks/{task_id}")
    client.get("/tasks")

    with SessionLocal() as session:
        after_updated = session.get(Task, task_id).updated_at
        after = session.scalar(select(func.count()).select_from(Approval))
    assert after_updated == before_updated
    assert after == before
