import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from backend.agent.app import app
from backend.agent.service import get_runner
from backend.coreloop import ExecutionOutcome
from backend.db import SessionLocal
from backend.models import Execution, Task

_OUTCOME = ExecutionOutcome(
    status="submitted", trip_id=42, trip_created=True, executed_steps=11, final_screen="submitted"
)
_ORDER = ["task_created", "execution_started", "execution_finished", "status_changed"]


@pytest.fixture
def client():
    test_client = TestClient(app)
    app.dependency_overrides[get_runner] = lambda: (lambda request: _OUTCOME)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()
        with SessionLocal() as session:
            session.execute(delete(Execution))
            session.execute(delete(Task))
            session.commit()


def _create(client: TestClient, dedup_key: str) -> dict:
    response = client.post(
        "/tasks",
        json={"workflow": "shukko", "instruction": "出張申請", "fields": {"dest": "大阪"}, "dedup_key": dedup_key},
    )
    return response.json()


def test_progress_during_disconnect_is_not_replayed_on_reconnect(client):
    with client.websocket_connect("/ws/agent") as ws:
        observed_task = _create(client, "task:A")
        observed = [ws.receive_json() for _ in range(4)]
        assert [event["type"] for event in observed] == _ORDER
        assert all(event["task_id"] == observed_task["id"] for event in observed)

    missed_task = _create(client, "task:B")

    with client.websocket_connect("/ws/agent") as ws:
        post_reconnect_task = _create(client, "task:C")
        events = [ws.receive_json() for _ in range(4)]

    assert [event["type"] for event in events] == _ORDER
    assert all(event["task_id"] == post_reconnect_task["id"] for event in events)
    assert all(event["task_id"] != missed_task["id"] for event in events)
    seqs = [event["seq"] for event in events]
    assert seqs == sorted(seqs)


def test_hydration_restores_state_changed_while_disconnected(client):
    with client.websocket_connect("/ws/agent") as ws:
        pass

    missed_task = _create(client, "task:B")

    with client.websocket_connect("/ws/agent") as ws:
        hydrated = client.get(f"/tasks/{missed_task['id']}").json()

    assert hydrated["id"] == missed_task["id"]
    assert hydrated["status"] == "submitted"
    assert len(hydrated["executions"]) == 1
    execution = hydrated["executions"][0]
    assert execution["status"] == "submitted"
    assert execution["trip_id"] == 42
    assert execution["trip_created"] is True
    assert execution["finished_at"] is not None
