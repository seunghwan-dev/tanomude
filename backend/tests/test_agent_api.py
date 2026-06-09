import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend.agent.app import app
from backend.agent.service import get_runner
from backend.coreloop import CorrectionCandidate, ExecutionOutcome
from backend.db import SessionLocal
from backend.models import Execution, Task


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


def _body(**overrides) -> dict:
    payload = {"workflow": "shutchou", "instruction": "出張申請", "fields": {"dest": "大阪"}, "dedup_key": "task:1"}
    payload.update(overrides)
    return payload


def _counts() -> tuple[int, int]:
    with SessionLocal() as session:
        tasks = session.scalar(select(func.count()).select_from(Task))
        executions = session.scalar(select(func.count()).select_from(Execution))
    return tasks, executions


def test_post_persists_and_rolls_up_submitted(client):
    _use_runner(
        ExecutionOutcome(status="submitted", trip_id=42, trip_created=True, executed_steps=11, final_screen="submitted")
    )
    response = client.post("/tasks", json=_body())
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "submitted"
    assert len(body["executions"]) == 1
    execution = body["executions"][0]
    assert execution["status"] == "submitted"
    assert execution["trip_id"] == 42
    assert execution["trip_created"] is True
    assert execution["executed_steps"] == 11
    assert _counts() == (1, 1)


def test_post_rolls_up_refused(client):
    _use_runner(ExecutionOutcome(status="refused", executed_steps=0))
    body = client.post("/tasks", json=_body()).json()
    assert body["status"] == "refused"
    assert body["executions"][0]["status"] == "refused"


@pytest.mark.parametrize("execution_status", ["verify_failed", "rolled_back", "parse_failed"])
def test_post_rolls_up_failed(client, execution_status):
    candidate = (
        CorrectionCandidate(screen="confirm", expected="submitted", diffs=["screen:None"], replan_count=2)
        if execution_status == "rolled_back"
        else None
    )
    _use_runner(
        ExecutionOutcome(
            status=execution_status, executed_steps=3, final_screen="confirm", errors=["x"], correction_candidate=candidate
        )
    )
    body = client.post("/tasks", json=_body()).json()
    assert body["status"] == "failed"
    assert body["executions"][0]["status"] == execution_status
    if execution_status == "rolled_back":
        assert body["executions"][0]["correction_candidate"]["replan_count"] == 2


def test_get_hydration_returns_nested_dto(client):
    _use_runner(
        ExecutionOutcome(status="submitted", trip_id=7, trip_created=True, executed_steps=11, final_screen="submitted")
    )
    task_id = client.post("/tasks", json=_body(fields={"dest": "大阪", "proj_hint": "P-001"})).json()["id"]
    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    assert body["id"] == task_id
    assert body["fields"] == {"dest": "大阪", "proj_hint": "P-001"}
    assert isinstance(body["executions"], list)
    assert body["executions"][0]["trip_id"] == 7


def test_get_is_read_only(client):
    _use_runner(
        ExecutionOutcome(status="submitted", trip_id=1, trip_created=True, executed_steps=11, final_screen="submitted")
    )
    task_id = client.post("/tasks", json=_body()).json()["id"]
    with SessionLocal() as session:
        before = session.get(Task, task_id).updated_at
    counts_before = _counts()

    client.get(f"/tasks/{task_id}")
    client.get("/tasks")

    with SessionLocal() as session:
        after = session.get(Task, task_id).updated_at
    assert after == before
    assert _counts() == counts_before


def test_hydration_orders_multiple_executions(client):
    _use_runner(ExecutionOutcome(status="rolled_back", executed_steps=3, final_screen="aborted", errors=["x"]))
    task_id = client.post("/tasks", json=_body()).json()["id"]
    with SessionLocal() as session:
        session.add(Execution(task_id=task_id, attempt_no=2, status="rolled_back", executed_steps=3))
        session.add(Execution(task_id=task_id, attempt_no=3, status="submitted", executed_steps=11))
        session.commit()
    body = client.get(f"/tasks/{task_id}").json()
    assert [execution["attempt_no"] for execution in body["executions"]] == [1, 2, 3]


def test_runner_exception_finalizes_rows(client):
    def _raising_runner(request, observer=None):
        raise RuntimeError("boom")

    app.dependency_overrides[get_runner] = lambda: _raising_runner
    with pytest.raises(RuntimeError):
        client.post("/tasks", json=_body())

    with SessionLocal() as session:
        task = session.scalars(select(Task)).one()
        execution = session.scalars(select(Execution)).one()
    assert task.status == "failed"
    assert execution.status == "errored"
    assert execution.finished_at is not None


def test_get_missing_task_returns_404(client):
    assert client.get("/tasks/999999").status_code == 404
