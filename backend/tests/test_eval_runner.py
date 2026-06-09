import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend import eval_runner
from backend.agent.app import app
from backend.agent.service import get_execute_runner, get_plan_runner
from backend.coreloop import ExecutionOutcome
from backend.db import SessionLocal
from backend.eval_dataset import EVAL_CASES, seed_eval_cases
from backend.eval_runner import CaseResult, aggregate
from backend.models import Approval, AuditLog, EvalCase, EvalResult, EvalRun, Execution, Plan, Task
from backend.retrieval import RetrievedChunk
from backend.slotfill import FilledKeysequence, Slots, Step

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
PERFECT_TRIP = {
    "dest": "OSAKA",
    "dept_date": "2026-06-10",
    "ret_date": "2026-06-11",
    "days": 2,
    "purpose": "製品X納入調整",
    "proj": "P-001",
    "overseas": False,
}


def _case(case_id: str):
    return next(case for case in EVAL_CASES if case.case_id == case_id)


def _result(case_id, category, expected, actual, passed, step_count=None, field_accuracy=None) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        category=category,
        expected_outcome=expected,
        actual_outcome=actual,
        passed=passed,
        step_count=step_count,
        field_accuracy=field_accuracy,
    )


def test_aggregate_headline_metrics():
    results = [
        _result("n1", "normal", "submitted", "submitted", True, step_count=13, field_accuracy=1.0),
        _result("n2", "normal", "submitted", "再入力/コード確認", False, step_count=7),
        _result("e1", "empty", "refused", "refused", True),
        _result("w1", "wrong_code", "再入力/コード確認", "再入力/コード確認", True, step_count=9),
        _result("w2", "wrong_code", "再入力/コード確認", "submitted", False, step_count=13, field_accuracy=0.5),
        _result("d2", "duplicate", "idempotent", "idempotent", True),
    ]
    metrics = aggregate(results)
    assert metrics["success_rate"] == 0.5
    assert metrics["routing_accuracy"] == pytest.approx(2 / 3)
    assert metrics["field_accuracy"] == 0.75
    assert metrics["verify_pass_rate"] == 0.5
    assert metrics["avg_steps"] == 10.5


def test_aggregate_empty_metrics_are_null():
    metrics = aggregate([])
    assert metrics["success_rate"] is None
    assert metrics["field_accuracy"] is None
    assert metrics["avg_steps"] is None
    assert metrics["recovery_rate"] is None


def test_aggregate_recovery_rate():
    results = [
        _result("n1", "normal", "submitted", "submitted", True, step_count=10, field_accuracy=1.0),
        _result("e1", "empty", "refused", "refused", True),
        _result("t1", "transient", "submitted", "submitted", True, step_count=10, field_accuracy=1.0),
        _result("t2", "transient", "submitted", "submitted", True, step_count=10, field_accuracy=1.0),
        _result("t3", "transient", "要調査", "要調査", True, step_count=12),
        _result("t4", "transient", "要調査", "要調査", True, step_count=12),
    ]
    metrics = aggregate(results)
    assert metrics["recovery_rate"] == 0.5


def test_expected_fields_derivation():
    expected = eval_runner.expected_fields(_case("normal_01").input.fields)
    assert expected == {
        "dest": "OSAKA",
        "dept_date": "2026-06-10",
        "ret_date": "2026-06-11",
        "days": 2,
        "proj": "P-001",
        "purpose": "製品X納入調整",
    }


def test_field_accuracy_perfect_and_mismatch():
    fields = _case("normal_01").input.fields
    assert eval_runner.field_accuracy(PERFECT_TRIP, fields) == 1.0
    wrong = {**PERFECT_TRIP, "proj": "P-999"}
    assert eval_runner.field_accuracy(wrong, fields) == pytest.approx(5 / 6)


def test_outcome_from_execution_mapping():
    assert eval_runner.outcome_from_execution({"status": "submitted"}) == "submitted"
    assert eval_runner.outcome_from_execution(
        {"status": "rolled_back", "correction_candidate": {"bad_data": True}}
    ) == "再入力/コード確認"
    assert eval_runner.outcome_from_execution(
        {"status": "rolled_back", "correction_candidate": {"bad_data": False}}
    ) == "要調査"
    assert eval_runner.outcome_from_execution({"status": "verify_failed"}) == "verify_failed"


def test_deterministic_cases_exclude_transient():
    cases = eval_runner.deterministic_cases()
    assert len(cases) == 20
    assert all(case.category != "transient" for case in cases)


@pytest.fixture
def plat():
    client = TestClient(app)
    app.dependency_overrides[get_plan_runner] = lambda: (lambda request: (FILLED, GROUNDS))
    app.dependency_overrides[get_execute_runner] = lambda: (
        lambda request, filled, observer=None: SUBMITTED
    )
    try:
        yield client
    finally:
        app.dependency_overrides.clear()
        with SessionLocal() as session:
            session.execute(delete(AuditLog))
            session.execute(delete(Approval))
            session.execute(delete(Plan))
            session.execute(delete(Execution))
            session.execute(delete(Task))
            session.commit()


def test_duplicate_pair_order_and_idempotent(plat, monkeypatch):
    monkeypatch.setattr(eval_runner, "_get_trip", lambda mock_base, trip_id: PERFECT_TRIP)
    first = eval_runner.run_case(plat, "http://mock", _case("dup_first_01"), "eval:test:k")
    assert first.actual_outcome == "submitted"
    assert first.passed
    assert first.field_accuracy == 1.0
    assert first.step_count == 11

    second = eval_runner.run_case(plat, "http://mock", _case("dup_second_01"), "eval:test:k")
    assert second.actual_outcome == "idempotent"
    assert second.passed
    assert second.step_count is None


@pytest.fixture
def eval_env():
    client = TestClient(app)
    app.dependency_overrides[get_plan_runner] = lambda: (lambda request: (FILLED, GROUNDS))
    app.dependency_overrides[get_execute_runner] = lambda: (
        lambda request, filled, observer=None: SUBMITTED
    )
    with SessionLocal() as session:
        seed_eval_cases(session)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()
        with SessionLocal() as session:
            session.execute(delete(EvalResult))
            session.execute(delete(EvalRun))
            session.execute(delete(EvalCase))
            session.execute(delete(AuditLog))
            session.execute(delete(Approval))
            session.execute(delete(Plan))
            session.execute(delete(Execution))
            session.execute(delete(Task))
            session.commit()


def test_run_eval_records_errored_case_without_aborting(eval_env, monkeypatch):
    monkeypatch.setattr(eval_runner, "_get_trip", lambda mock_base, trip_id: PERFECT_TRIP)
    real_run_case = eval_runner.run_case

    def flaky(plat_client, mock_base, case, dedup_key):
        if case.case_id == "wrong_01_px":
            raise RuntimeError("trip fetch blip")
        return real_run_case(plat_client, mock_base, case, dedup_key)

    monkeypatch.setattr(eval_runner, "run_case", flaky)
    with SessionLocal() as db:
        run_id, results = eval_runner.run_eval(eval_env, db, "http://mock", "nonce")
        stored = db.scalar(select(func.count()).select_from(EvalResult).where(EvalResult.run_id == run_id))
    assert len(results) == 20
    assert stored == 20
    errored = [r for r in results if r.actual_outcome == "errored"]
    assert [r.case_id for r in errored] == ["wrong_01_px"]
    assert errored[0].passed is False
