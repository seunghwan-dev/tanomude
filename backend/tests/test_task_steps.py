from pathlib import Path

import app as app_pkg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import SessionLocal as MockSessionLocal
from app.main import app as mock_app
from app.models import MockSession, TripApplication
from adapter.mock_adapter import MockAdapter
from backend.agent.app import app
from backend.agent.observer import build_step_observer, derive_intent
from backend.agent.service import get_runner
from backend.coreloop import plan, run_task
from backend.db import SessionLocal
from backend.models import Execution, Task, TaskStep
from backend.slotfill import RequestInput, Slots

MOCK_ROOT = Path(app_pkg.__file__).resolve().parent.parent
SLOTS = Slots(dest_code="OSAKA", purpose="製品X納入調整")


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


def _wipe() -> None:
    with SessionLocal() as session:
        session.execute(delete(TaskStep))
        session.execute(delete(Execution))
        session.execute(delete(Task))
        session.commit()


@pytest.fixture(autouse=True)
def clean_platform():
    _wipe()
    yield
    _wipe()
    app.dependency_overrides.clear()


def _request(**overrides) -> RequestInput:
    fields = {"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11", "proj_hint": "P-001"}
    fields.update(overrides)
    return RequestInput(workflow="shukko", instruction="出張申請", fields=fields)


def _constant(slots: Slots):
    return lambda request, context: slots


def _seed_task_execution() -> tuple[int, int]:
    with SessionLocal() as db:
        task = Task(workflow="shukko", instruction="出張申請", fields={"dest": "大阪"}, status="running")
        db.add(task)
        db.commit()
        db.refresh(task)
        execution = Execution(task_id=task.id, attempt_no=1, status="running", executed_steps=0)
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return task.id, execution.id


def _steps(execution_id: int) -> list[TaskStep]:
    with SessionLocal() as db:
        return list(
            db.scalars(select(TaskStep).where(TaskStep.execution_id == execution_id).order_by(TaskStep.ordinal))
        )


def _step_count() -> int:
    with SessionLocal() as db:
        return len(list(db.scalars(select(TaskStep))))


def test_derive_intent_japanese_labels():
    assert derive_intent({"type": "field", "target": "DEST"}) == "目的地コード入力"
    assert derive_intent({"type": "field", "target": "PURPOSE"}) == "目的入力"
    assert derive_intent({"type": "fkey", "key": "F4"}) == "案件コード選択"
    assert derive_intent({"type": "nav", "key": "Enter"}) == "画面遷移"
    assert derive_intent({"type": "fkey", "key": "Enter"}) == "確定"


def test_observer_persists_steps_in_order(mock_client):
    task_id, execution_id = _seed_task_execution()
    emitted: list[dict] = []
    observer = build_step_observer(execution_id, task_id, emit=lambda et, tid, payload: emitted.append(payload))

    outcome = run_task(_request(), MockAdapter(mock_client), _constant(SLOTS), observer=observer)

    assert outcome.status == "submitted"
    steps = _steps(execution_id)
    assert [step.ordinal for step in steps] == list(range(1, 11))
    assert all(step.status == "ok" for step in steps)
    assert any(step.action["target"] == "DEST" for step in steps)
    assert steps[1].intent == "目的地コード入力"
    assert [payload["ordinal"] for payload in emitted] == [step.ordinal for step in steps]


def test_step_committed_before_emit(mock_client):
    task_id, execution_id = _seed_task_execution()
    visible: list[bool] = []

    def emit(event_type, tid, payload):
        with SessionLocal() as probe:
            row = probe.scalars(
                select(TaskStep).where(
                    TaskStep.execution_id == execution_id, TaskStep.ordinal == payload["ordinal"]
                )
            ).first()
        visible.append(row is not None)

    observer = build_step_observer(execution_id, task_id, emit=emit)
    run_task(_request(), MockAdapter(mock_client), _constant(SLOTS), observer=observer)

    assert visible
    assert all(visible)


def test_no_observer_writes_no_steps(mock_client):
    plan(_request(), _constant(SLOTS), "")
    outcome = run_task(_request(), MockAdapter(mock_client), _constant(SLOTS))
    assert outcome.status == "submitted"
    assert _step_count() == 0


def test_bad_data_step_lands_on_timeline(mock_client):
    task_id, execution_id = _seed_task_execution()
    emitted: list[dict] = []
    observer = build_step_observer(execution_id, task_id, emit=lambda et, tid, payload: emitted.append(payload))

    outcome = run_task(_request(proj_hint="PX-001"), MockAdapter(mock_client), _constant(SLOTS), observer=observer)

    assert outcome.status == "rolled_back"
    assert outcome.correction_candidate.bad_data is True
    steps = _steps(execution_id)
    assert steps[-1].status == "error"
    assert "PROJ_format" in steps[-1].errors
    assert steps[-1].action["key"] == "Enter"
    assert len(emitted) == len(steps)
    assert emitted[-1]["status"] == "error"


def test_hydration_includes_steps_so_far(mock_client):
    def stepping_runner(request, observer=None):
        return run_task(request, MockAdapter(mock_client), _constant(SLOTS), observer=observer)

    app.dependency_overrides[get_runner] = lambda: stepping_runner
    body = {
        "workflow": "shukko",
        "instruction": "出張申請",
        "fields": {"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11", "proj_hint": "P-001"},
        "dedup_key": "task:steps",
    }
    with TestClient(app) as api_client:
        task_id = api_client.post("/tasks", json=body).json()["id"]
        hydrated = api_client.get(f"/tasks/{task_id}").json()
    steps = hydrated["executions"][0]["steps"]
    assert [step["ordinal"] for step in steps] == list(range(1, 11))
    assert steps[1]["intent"] == "目的地コード入力"
    assert steps[-1]["status"] == "ok"


def test_step_executed_broadcast_over_ws(mock_client):
    def stepping_runner(request, observer=None):
        return run_task(request, MockAdapter(mock_client), _constant(SLOTS), observer=observer)

    app.dependency_overrides[get_runner] = lambda: stepping_runner
    body = {
        "workflow": "shukko",
        "instruction": "出張申請",
        "fields": {"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11", "proj_hint": "P-001"},
        "dedup_key": "task:ws",
    }
    with TestClient(app) as api_client, api_client.websocket_connect("/ws/agent") as ws:
        api_client.post("/tasks", json=body)
        events = []
        while True:
            event = ws.receive_json()
            events.append(event)
            if event["type"] == "status_changed":
                break

    types = [event["type"] for event in events]
    step_events = [event for event in events if event["type"] == "step_executed"]
    assert [event["payload"]["ordinal"] for event in step_events] == list(range(1, 11))
    last_step_index = max(index for index, name in enumerate(types) if name == "step_executed")
    assert types.index("execution_started") < last_step_index
    assert types.index("execution_finished") > last_step_index
