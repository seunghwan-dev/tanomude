import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend.agent import repository
from backend.agent.app import app
from backend.agent.manager import manager
from backend.agent.service import get_execute_runner, get_plan_runner, get_revise_assessor, get_runner
from backend.coreloop import ExecutionOutcome
from backend.corrections import MAX_CORRECTION_LENGTH, apply_corrections
from backend.db import SessionLocal
from backend.models import Approval, AuditLog, Execution, PersonalCorrection, Plan, Task
from backend.retrieval import RetrievedChunk
from backend.slotfill import FilledKeysequence, ReviseAssessment, Slots, Step

SLOTS = Slots(dest_code="OSAKA", purpose="製品X納入調整")
STEPS = [
    Step(seq=1, type="nav", key="Enter"),
    Step(seq=2, type="field", target="DEST", value="OSAKA"),
]
FILLED = FilledKeysequence(workflow="shutchou", steps=STEPS, slots=SLOTS)
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
            session.execute(delete(PersonalCorrection))
            session.execute(delete(Plan))
            session.execute(delete(Execution))
            session.execute(delete(Task))
            session.commit()


def _seed_awaiting(client, dedup_key: str = "task:dec:1", dest: str = "大阪") -> int:
    app.dependency_overrides[get_plan_runner] = lambda: (lambda request: (FILLED, GROUNDS))
    body = {"workflow": "shutchou", "instruction": "出張申請", "fields": {"dest": dest}, "dedup_key": dedup_key}
    return client.post("/tasks/plan", json=body).json()["task"]["id"]


def _use_execute_runner(outcome: ExecutionOutcome) -> None:
    app.dependency_overrides[get_execute_runner] = lambda: (lambda request, filled, observer=None: outcome)


def _use_revise_assessor(persist: bool, blocked_slot: str | None = None) -> None:
    app.dependency_overrides[get_revise_assessor] = lambda: (
        lambda request, decision_text: ReviseAssessment(persist=persist, blocked_slot=blocked_slot)
    )


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

    def _raising(request, filled, observer=None):
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


def test_approve_maps_upstream_http_error_to_502(client):
    task_id = _seed_awaiting(client)

    def _raising(request, filled, observer=None):
        http_request = httpx.Request("POST", "http://localhost:8400/session")
        raise httpx.HTTPStatusError(
            "not found", request=http_request, response=httpx.Response(404, request=http_request)
        )

    app.dependency_overrides[get_execute_runner] = lambda: _raising
    response = client.post(f"/tasks/{task_id}/approve", json={"approver": "tanaka"})
    assert response.status_code == 502
    assert response.json()["detail"] == "upstream 404 at http://localhost:8400/session"
    with SessionLocal() as session:
        assert session.get(Task, task_id).status == "failed"
        execution = session.scalars(select(Execution).where(Execution.task_id == task_id)).one()
        assert execution.status == "errored"


def test_approve_maps_upstream_connect_error_to_502(client):
    task_id = _seed_awaiting(client)

    def _raising(request, filled, observer=None):
        http_request = httpx.Request("POST", "http://localhost:8400/session")
        raise httpx.ConnectError("connection refused", request=http_request)

    app.dependency_overrides[get_execute_runner] = lambda: _raising
    response = client.post(f"/tasks/{task_id}/approve", json={"approver": "tanaka"})
    assert response.status_code == 502
    assert response.json()["detail"] == "upstream unreachable at http://localhost:8400/session"


def test_create_task_maps_upstream_http_error_to_502(client):
    def _raising(request, observer=None):
        http_request = httpx.Request("POST", "http://localhost:8001/embed")
        raise httpx.HTTPStatusError(
            "down", request=http_request, response=httpx.Response(503, request=http_request)
        )

    app.dependency_overrides[get_runner] = lambda: _raising
    body = {"workflow": "shutchou", "instruction": "出張申請", "fields": {"dest": "大阪"}, "dedup_key": "task:create:err"}
    response = client.post("/tasks", json=body)
    assert response.status_code == 502
    assert response.json()["detail"] == "upstream 503 at http://localhost:8001/embed"


def test_approve_non_mock_error_is_not_mapped_to_gateway(client):
    task_id = _seed_awaiting(client)

    def _raising(request, filled, observer=None):
        raise RuntimeError("boom")

    app.dependency_overrides[get_execute_runner] = lambda: _raising
    with pytest.raises(RuntimeError):
        client.post(f"/tasks/{task_id}/approve", json={"approver": "tanaka"})


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
        correction = session.scalars(select(PersonalCorrection)).one()
        assert correction.source == "human_reject"
        assert correction.trigger == {"dest": "大阪"}
        assert correction.correction_text == "案件コード誤り"
        assert correction.status == "active"
        assert correction.approver == "tanaka"


def test_revise_records_approval_row_keeps_awaiting_and_no_new_plan(client):
    task_id = _seed_awaiting(client)
    _use_revise_assessor(True)
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
        correction = session.scalars(select(PersonalCorrection)).one()
        assert correction.source == "human_revise"
        assert correction.trigger == {"dest": "大阪"}
        assert correction.correction_text == "目的を具体化して"
        assert correction.status == "active"
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


def _raise_after_staging(monkeypatch):
    real_stage = repository._stage_decision

    def boom(db, task, plan_id, decision, approver, decision_text):
        real_stage(db, task, plan_id, decision, approver, decision_text)
        raise RuntimeError("mid-decision crash")

    monkeypatch.setattr(repository, "_stage_decision", boom)


def test_approve_rolls_back_entirely_on_midwrite_failure(client, monkeypatch):
    task_id = _seed_awaiting(client)
    _raise_after_staging(monkeypatch)
    with pytest.raises(RuntimeError):
        client.post(f"/tasks/{task_id}/approve", json={"approver": "tanaka"})
    with SessionLocal() as session:
        assert session.scalar(
            select(func.count()).select_from(Approval).where(Approval.task_id == task_id)
        ) == 0
        assert session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.task_id == task_id)
        ) == 0
        assert session.scalar(
            select(func.count()).select_from(Execution).where(Execution.task_id == task_id)
        ) == 0
        assert session.get(Task, task_id).status == "awaiting_approval"


def test_reject_rolls_back_entirely_on_midwrite_failure(client, monkeypatch):
    task_id = _seed_awaiting(client)
    _raise_after_staging(monkeypatch)
    with pytest.raises(RuntimeError):
        client.post(f"/tasks/{task_id}/reject", json={"approver": "tanaka", "decision_text": "x"})
    with SessionLocal() as session:
        assert session.scalar(
            select(func.count()).select_from(Approval).where(Approval.task_id == task_id)
        ) == 0
        assert session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.task_id == task_id)
        ) == 0
        assert session.get(Task, task_id).status == "awaiting_approval"


@pytest.mark.parametrize("exec_status", ["verify_failed", "rolled_back"])
def test_approve_failed_outcome_rolls_up_to_failed(client, exec_status):
    task_id = _seed_awaiting(client)
    _use_execute_runner(
        ExecutionOutcome(status=exec_status, executed_steps=3, final_screen="confirm", errors=["x"])
    )
    with client.websocket_connect("/ws/agent") as ws:
        response = client.post(f"/tasks/{task_id}/approve", json={"approver": "tanaka"})
        events = [ws.receive_json() for _ in range(4)]
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["executions"][0]["status"] == exec_status
    assert events[3]["type"] == "status_changed"
    assert events[3]["payload"]["status"] == "failed"
    with SessionLocal() as session:
        assert session.get(Task, task_id).status == "failed"


def test_get_after_decision_is_read_only(client):
    task_id = _seed_awaiting(client)
    _use_revise_assessor(True)
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


def test_reject_without_decision_text_persists_no_correction(client):
    task_id = _seed_awaiting(client)
    response = client.post(f"/tasks/{task_id}/reject", json={"approver": "tanaka"})
    assert response.status_code == 200
    with SessionLocal() as session:
        assert session.scalars(select(Approval).where(Approval.task_id == task_id)).one().decision == "reject"
        assert session.scalar(select(func.count()).select_from(PersonalCorrection)) == 0


def test_reject_correction_feeds_next_plan_for_same_destination(client):
    task_id = _seed_awaiting(client)
    reuse_text = "前回案件コードを再利用し reuse_prev_proj を true に上書きすること。"
    client.post(f"/tasks/{task_id}/reject", json={"approver": "tanaka", "decision_text": reuse_text})
    with SessionLocal() as session:
        context, fallback = apply_corrections(session, "shutchou", {"dest": "大阪"}, "RAG-BASE")
    assert reuse_text in context
    assert fallback == []


@pytest.mark.parametrize("action", ["approve", "reject", "revise"])
@pytest.mark.parametrize(
    "bad_text", ["x" * (MAX_CORRECTION_LENGTH + 1), "汚染\x07注入"], ids=["too_long", "control_char"]
)
def test_decision_text_rejected_when_unbounded_or_control(client, action, bad_text):
    task_id = _seed_awaiting(client)
    response = client.post(
        f"/tasks/{task_id}/{action}", json={"approver": "tanaka", "decision_text": bad_text}
    )
    assert response.status_code == 422
    with SessionLocal() as session:
        assert session.scalar(
            select(func.count()).select_from(Approval).where(Approval.task_id == task_id)
        ) == 0
        assert session.scalar(select(func.count()).select_from(PersonalCorrection)) == 0
        assert session.get(Task, task_id).status == "awaiting_approval"


def test_reject_correction_rolls_back_atomically_with_decision(client, monkeypatch):
    task_id = _seed_awaiting(client)
    real_stage = repository.stage_correction

    def boom(*args, **kwargs):
        real_stage(*args, **kwargs)
        raise RuntimeError("mid-correction crash")

    monkeypatch.setattr(repository, "stage_correction", boom)
    with pytest.raises(RuntimeError):
        client.post(
            f"/tasks/{task_id}/reject", json={"approver": "tanaka", "decision_text": "案件コード誤り"}
        )
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(PersonalCorrection)) == 0
        assert session.scalar(
            select(func.count()).select_from(Approval).where(Approval.task_id == task_id)
        ) == 0
        assert session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.task_id == task_id)
        ) == 0
        assert session.get(Task, task_id).status == "awaiting_approval"


def test_revise_correction_rolls_back_atomically_with_decision(client, monkeypatch):
    task_id = _seed_awaiting(client)
    _use_revise_assessor(True)
    real_stage = repository.stage_correction

    def boom(*args, **kwargs):
        real_stage(*args, **kwargs)
        raise RuntimeError("mid-correction crash")

    monkeypatch.setattr(repository, "stage_correction", boom)
    with pytest.raises(RuntimeError):
        client.post(
            f"/tasks/{task_id}/revise", json={"approver": "tanaka", "decision_text": "目的を具体化して"}
        )
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(PersonalCorrection)) == 0
        assert session.scalar(
            select(func.count()).select_from(Approval).where(Approval.task_id == task_id)
        ) == 0
        assert session.get(Task, task_id).status == "awaiting_approval"


def test_repeated_reject_same_destination_supersedes_correction(client):
    t1 = _seed_awaiting(client, dedup_key="task:sup:1", dest="大阪")
    client.post(f"/tasks/{t1}/reject", json={"approver": "tanaka", "decision_text": "最初の修正"})
    t2 = _seed_awaiting(client, dedup_key="task:sup:2", dest="大阪")
    client.post(f"/tasks/{t2}/reject", json={"approver": "tanaka", "decision_text": "二回目の修正"})
    with SessionLocal() as session:
        active = session.scalars(
            select(PersonalCorrection).where(PersonalCorrection.status == "active")
        ).one()
        superseded = session.scalars(
            select(PersonalCorrection).where(PersonalCorrection.status == "superseded")
        ).one()
        assert active.correction_text == "二回目の修正"
        assert active.version == 2
        assert superseded.correction_text == "最初の修正"
        assert active.supersedes_id == superseded.id


def test_revise_blocked_grounded_slot_surfaces_notice_and_persists_no_correction(client):
    task_id = _seed_awaiting(client)
    _use_revise_assessor(False, blocked_slot="目的地")
    response = client.post(
        f"/tasks/{task_id}/revise", json={"approver": "tanaka", "decision_text": "目的地を神戸に変更"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "awaiting_approval"
    assert body["revise_notice"] == (
        "申し訳ありません。目的地は指示文で確定する項目のため、修正では変更できません。"
        "変更したい場合は、新しい指示でやり直してください。"
    )
    with SessionLocal() as session:
        assert session.scalars(select(Approval).where(Approval.task_id == task_id)).one().decision == "revise"
        assert session.scalar(select(func.count()).select_from(PersonalCorrection)) == 0
        assert session.get(Task, task_id).status == "awaiting_approval"


def test_revise_movable_change_persists_correction_without_notice(client):
    task_id = _seed_awaiting(client)
    _use_revise_assessor(True)
    response = client.post(
        f"/tasks/{task_id}/revise", json={"approver": "tanaka", "decision_text": "前回の案件を再利用"}
    )
    assert response.status_code == 200
    assert response.json()["revise_notice"] is None
    with SessionLocal() as session:
        correction = session.scalars(select(PersonalCorrection)).one()
        assert correction.source == "human_revise"
        assert correction.status == "active"


def test_blocked_revise_preserves_existing_active_correction(client):
    t1 = _seed_awaiting(client, dedup_key="task:imm:1", dest="大阪")
    _use_revise_assessor(True)
    client.post(f"/tasks/{t1}/revise", json={"approver": "tanaka", "decision_text": "前回の案件を再利用"})
    t2 = _seed_awaiting(client, dedup_key="task:imm:2", dest="大阪")
    _use_revise_assessor(False, blocked_slot="目的地")
    client.post(f"/tasks/{t2}/revise", json={"approver": "tanaka", "decision_text": "目的地を神戸に変更"})
    with SessionLocal() as session:
        actives = session.scalars(
            select(PersonalCorrection).where(PersonalCorrection.status == "active")
        ).all()
        assert len(actives) == 1
        assert actives[0].correction_text == "前回の案件を再利用"
        assert session.scalar(select(func.count()).select_from(PersonalCorrection)) == 1
