import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend.agent.app import app
from backend.agent.manager import manager
from backend.agent.service import ParseFailure, get_plan_runner
from backend.db import SessionLocal
from backend.models import Approval, AuditLog, Execution, Plan, Task
from backend.retrieval import RetrievedChunk
from backend.slotfill import FilledKeysequence, Refusal, Slots, Step

SLOTS = Slots(dest_code="OSAKA", purpose="製品X納入調整")
STEPS = [
    Step(seq=1, type="nav", key="Enter"),
    Step(seq=2, type="field", target="DEST", value="OSAKA"),
]
FILLED = FilledKeysequence(workflow="shutchou", steps=STEPS, slots=SLOTS)
GROUNDS = [
    RetrievedChunk(chunk_id=3, doc_id=1, section="apply", heading="申請手順", text="F4で案件を選ぶ", score=0.42, rank=1)
]


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


def _use_plan_runner(value) -> None:
    app.dependency_overrides[get_plan_runner] = lambda: (lambda request: value)


def _body(**overrides) -> dict:
    payload = {"workflow": "shutchou", "instruction": "出張申請", "fields": {"dest": "大阪"}, "dedup_key": "task:plan:1"}
    payload.update(overrides)
    return payload


def test_plan_persists_proposed_and_returns_plan_view(client):
    _use_plan_runner((FILLED, GROUNDS))
    response = client.post("/tasks/plan", json=_body())
    assert response.status_code == 201
    body = response.json()
    assert body["task"]["status"] == "awaiting_approval"
    plan_view = body["plan"]
    assert plan_view is not None
    assert plan_view["version"] == 1
    assert plan_view["status"] == "proposed"
    assert plan_view["analysis"]["dest_code"] == "OSAKA"
    assert plan_view["keysequence"][0]["key"] == "Enter"
    assert plan_view["grounding"][0]["heading"] == "申請手順"

    with SessionLocal() as session:
        plan = session.scalars(select(Plan)).one()
        assert plan.task_id == body["task"]["id"]
        assert plan.version == 1
        assert plan.status == "proposed"
        assert plan.analysis == SLOTS.model_dump()
        assert plan.keysequence == [step.model_dump() for step in STEPS]
        task = session.get(Task, body["task"]["id"])
        assert task.status == "awaiting_approval"


def test_plan_grounds_persist_as_retrieved_chunk_dump(client):
    _use_plan_runner((FILLED, GROUNDS))
    task_id = client.post("/tasks/plan", json=_body()).json()["task"]["id"]
    with SessionLocal() as session:
        plan = session.scalars(select(Plan).where(Plan.task_id == task_id)).one()
    assert plan.grounding == [chunk.model_dump() for chunk in GROUNDS]
    assert plan.grounding[0]["score"] == 0.42
    assert plan.grounding[0]["chunk_id"] == 3


def test_plan_refusal_marks_refused_without_persisting_plan(client):
    _use_plan_runner((Refusal(reason="required fields missing", missing_fields=["DEST"]), []))
    response = client.post("/tasks/plan", json=_body(fields={}))
    assert response.status_code == 201
    body = response.json()
    assert body["task"]["status"] == "refused"
    assert body["plan"] is None
    assert body["refusal"]["reason"] == "required fields missing"
    assert body["refusal"]["missing_fields"] == ["DEST"]
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(Plan)) == 0


def test_parse_failure_marks_failed_without_persisting_plan(client):
    app.dependency_overrides[get_plan_runner] = lambda: (
        lambda request: (ParseFailure(errors=["unparseable slots"]), GROUNDS)
    )
    response = client.post("/tasks/plan", json=_body())
    assert response.status_code == 201
    body = response.json()
    assert body["task"]["status"] == "failed"
    assert body["plan"] is None
    assert body["refusal"] is None
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(Plan)) == 0


def test_parse_failure_broadcasts_parse_failed_reason(client):
    app.dependency_overrides[get_plan_runner] = lambda: (
        lambda request: (ParseFailure(errors=["unparseable slots"]), GROUNDS)
    )
    with client.websocket_connect("/ws/agent") as ws:
        client.post("/tasks/plan", json=_body())
        events = [ws.receive_json() for _ in range(2)]
    assert [event["type"] for event in events] == ["task_created", "status_changed"]
    assert events[1]["payload"]["status"] == "failed"
    assert events[1]["payload"]["reason"] == "parse_failed"


def test_plan_runner_exception_marks_task_errored_not_orphan(client):
    def _raising(request):
        raise RuntimeError("boom")

    app.dependency_overrides[get_plan_runner] = lambda: _raising

    with client.websocket_connect("/ws/agent") as ws:
        with pytest.raises(RuntimeError):
            client.post("/tasks/plan", json=_body())
        events = [ws.receive_json() for _ in range(2)]

    assert [event["type"] for event in events] == ["task_created", "status_changed"]
    assert events[1]["payload"]["status"] == "errored"
    with SessionLocal() as session:
        task = session.scalars(select(Task)).one()
        assert task.status == "errored"
        assert session.scalar(select(func.count()).select_from(Plan)) == 0


def test_plan_ready_broadcast_after_task_created(client):
    _use_plan_runner((FILLED, GROUNDS))
    with client.websocket_connect("/ws/agent") as ws:
        client.post("/tasks/plan", json=_body())
        events = [ws.receive_json() for _ in range(2)]
    assert [event["type"] for event in events] == ["task_created", "plan_ready"]
    assert events[1]["payload"]["status"] == "proposed"
    assert events[1]["payload"]["analysis"]["dest_code"] == "OSAKA"


def test_refusal_broadcasts_status_changed_not_plan_ready(client):
    _use_plan_runner((Refusal(reason="missing", missing_fields=["DEST"]), []))
    with client.websocket_connect("/ws/agent") as ws:
        client.post("/tasks/plan", json=_body(fields={}))
        events = [ws.receive_json() for _ in range(2)]
    assert [event["type"] for event in events] == ["task_created", "status_changed"]
    assert events[1]["payload"]["status"] == "refused"
    assert events[1]["payload"]["reason"] == "missing"


def test_plan_commit_precedes_broadcast(client, monkeypatch):
    _use_plan_runner((FILLED, GROUNDS))
    observations: list[tuple] = []
    original = manager.broadcast

    async def spy(event_type, task_id, payload):
        if event_type == "plan_ready":
            with SessionLocal() as session:
                count = session.scalar(
                    select(func.count()).select_from(Plan).where(Plan.task_id == task_id)
                )
            observations.append(count)
        await original(event_type, task_id, payload)

    monkeypatch.setattr(manager, "broadcast", spy)

    with client.websocket_connect("/ws/agent") as ws:
        client.post("/tasks/plan", json=_body())
        [ws.receive_json() for _ in range(2)]

    assert observations == [1]


def test_get_task_plan_returns_proposed_plan(client):
    _use_plan_runner((FILLED, GROUNDS))
    task_id = client.post("/tasks/plan", json=_body()).json()["task"]["id"]
    response = client.get(f"/tasks/{task_id}/plan")
    assert response.status_code == 200
    body = response.json()
    assert body["task"]["id"] == task_id
    assert body["task"]["status"] == "awaiting_approval"
    assert body["plan"]["status"] == "proposed"
    assert body["plan"]["analysis"]["dest_code"] == "OSAKA"
    assert body["plan"]["keysequence"][0]["key"] == "Enter"


def test_get_task_plan_404_for_missing_task(client):
    assert client.get("/tasks/999999/plan").status_code == 404


def test_get_after_plan_is_read_only(client):
    _use_plan_runner((FILLED, GROUNDS))
    task_id = client.post("/tasks/plan", json=_body()).json()["task"]["id"]
    with SessionLocal() as session:
        before_updated = session.get(Task, task_id).updated_at
        before = (
            session.scalar(select(func.count()).select_from(Task)),
            session.scalar(select(func.count()).select_from(Plan)),
        )

    client.get(f"/tasks/{task_id}")
    client.get("/tasks")

    with SessionLocal() as session:
        after_updated = session.get(Task, task_id).updated_at
        after = (
            session.scalar(select(func.count()).select_from(Task)),
            session.scalar(select(func.count()).select_from(Plan)),
        )
    assert after_updated == before_updated
    assert after == before
