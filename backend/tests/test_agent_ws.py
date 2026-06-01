import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend.agent.app import app
from backend.agent.manager import manager
from backend.agent.service import get_runner
from backend.coreloop import ExecutionOutcome
from backend.db import SessionLocal
from backend.models import Execution, Task

_SUBMITTED = ExecutionOutcome(
    status="submitted", trip_id=1, trip_created=True, executed_steps=11, final_screen="submitted"
)
_ORDER = ["task_created", "execution_started", "execution_finished", "status_changed"]


@pytest.fixture
def client():
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()
        with SessionLocal() as session:
            session.execute(delete(Execution))
            session.execute(delete(Task))
            session.commit()


def _use_runner(outcome: ExecutionOutcome) -> None:
    app.dependency_overrides[get_runner] = lambda: (lambda request, observer=None: outcome)


def _body() -> dict:
    return {"workflow": "shukko", "instruction": "出張申請", "fields": {"dest": "大阪"}, "dedup_key": "task:1"}


def test_event_order_and_monotonic_seq(client):
    _use_runner(_SUBMITTED)
    with client.websocket_connect("/ws/agent") as ws:
        task_id = client.post("/tasks", json=_body()).json()["id"]
        events = [ws.receive_json() for _ in range(4)]
    assert [event["type"] for event in events] == _ORDER
    seqs = [event["seq"] for event in events]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == 4
    assert all(event["task_id"] == task_id for event in events)
    assert all("ts" in event for event in events)
    assert events[2]["payload"]["status"] == "submitted"
    assert events[3]["payload"]["status"] == "submitted"


def test_commit_precedes_broadcast(client, monkeypatch):
    _use_runner(_SUBMITTED)
    observations: list[tuple] = []
    original = manager.broadcast

    async def spy(event_type, task_id, payload):
        with SessionLocal() as session:
            task = session.get(Task, task_id)
            task_status = task.status if task is not None else None
            execution_status = None
            if task is not None:
                execution = session.scalars(
                    select(Execution).where(Execution.task_id == task_id).order_by(Execution.id.desc())
                ).first()
                execution_status = execution.status if execution is not None else None
        observations.append((event_type, task_status, execution_status))
        await original(event_type, task_id, payload)

    monkeypatch.setattr(manager, "broadcast", spy)

    with client.websocket_connect("/ws/agent") as ws:
        client.post("/tasks", json=_body())
        [ws.receive_json() for _ in range(4)]

    assert [event_type for event_type, _, _ in observations] == _ORDER
    assert all(task_status is not None for _, task_status, _ in observations)
    assert all(execution_status is not None for event_type, _, execution_status in observations
               if event_type != "task_created")
    finished = dict((event_type, (task_status, execution_status)) for event_type, task_status, execution_status in observations)
    assert finished["execution_finished"][1] == "submitted"
    assert finished["status_changed"][0] == "submitted"


def test_multiple_clients_receive(client):
    _use_runner(_SUBMITTED)
    with client.websocket_connect("/ws/agent") as ws_a, client.websocket_connect("/ws/agent") as ws_b:
        client.post("/tasks", json=_body())
        types_a = [ws_a.receive_json()["type"] for _ in range(4)]
        types_b = [ws_b.receive_json()["type"] for _ in range(4)]
    assert types_a == _ORDER
    assert types_b == _ORDER


def test_ws_connection_does_not_write(client):
    _use_runner(_SUBMITTED)
    client.post("/tasks", json=_body())
    with SessionLocal() as session:
        before = (
            session.scalar(select(func.count()).select_from(Task)),
            session.scalar(select(func.count()).select_from(Execution)),
        )
    with client.websocket_connect("/ws/agent") as ws:
        ws.send_text("ping")
    with SessionLocal() as session:
        after = (
            session.scalar(select(func.count()).select_from(Task)),
            session.scalar(select(func.count()).select_from(Execution)),
        )
    assert after == before
