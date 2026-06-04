import pytest
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from backend.db import SessionLocal
from backend.eval_dataset import (
    EVAL_CASES,
    EvalCaseInput,
    EvalCaseSeed,
    seed_eval_cases,
)
from backend.models import EvalCase, EvalResult, EvalRun

EXPECTED_COUNTS = {"normal": 8, "empty": 4, "wrong_code": 4, "transient": 4, "duplicate": 4}
OUTCOMES = {"submitted", "再入力/コード確認", "要調査", "refused", "idempotent"}


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.execute(delete(EvalResult))
        db.execute(delete(EvalRun))
        db.execute(delete(EvalCase))
        db.commit()
        db.close()


def test_seed_loads_all_cases(session):
    count = seed_eval_cases(session)
    assert count == 24
    assert session.scalar(select(func.count()).select_from(EvalCase)) == 24


def test_category_counts(session):
    seed_eval_cases(session)
    rows = session.execute(select(EvalCase.category, func.count()).group_by(EvalCase.category)).all()
    counts = {category: total for category, total in rows}
    assert counts == EXPECTED_COUNTS


def test_every_case_has_valid_input_and_outcome(session):
    seed_eval_cases(session)
    cases = session.scalars(select(EvalCase)).all()
    assert len(cases) == 24
    for case in cases:
        parsed = EvalCaseInput.model_validate(case.input)
        assert parsed.workflow == "shukko"
        assert isinstance(parsed.fields, dict)
        assert case.category in EXPECTED_COUNTS
        assert case.expected_outcome in OUTCOMES


def test_expected_outcomes_match_category_semantics():
    by_category: dict[str, list[str]] = {}
    for case in EVAL_CASES:
        by_category.setdefault(case.category, []).append(case.expected_outcome)
    assert set(by_category["normal"]) == {"submitted"}
    assert set(by_category["empty"]) == {"refused"}
    assert set(by_category["wrong_code"]) == {"再入力/コード確認"}
    assert sorted(by_category["transient"]) == sorted(["submitted", "submitted", "要調査", "要調査"])
    assert sorted(by_category["duplicate"]) == sorted(["submitted", "submitted", "idempotent", "idempotent"])


def test_duplicate_pairs_share_dedup_key():
    duplicates = [case for case in EVAL_CASES if case.category == "duplicate"]
    keyed: dict[str, list[str]] = {}
    for case in duplicates:
        assert case.input.dedup_key is not None
        keyed.setdefault(case.input.dedup_key, []).append(case.expected_outcome)
    for outcomes in keyed.values():
        assert sorted(outcomes) == ["idempotent", "submitted"]


def test_result_references_run_and_case(session):
    seed_eval_cases(session)
    run = EvalRun(config={"model": "test", "corrections_applied": False, "k": 3, "transient_inject": False})
    session.add(run)
    session.flush()
    case = session.scalars(select(EvalCase).where(EvalCase.case_id == "normal_01")).one()
    result = EvalResult(
        run_id=run.run_id,
        case_id=case.case_id,
        actual_outcome="submitted",
        passed=True,
        field_accuracy=1.0,
        step_count=13,
        replan_count=0,
    )
    session.add(result)
    session.commit()
    session.refresh(result)
    assert result.run.run_id == run.run_id
    assert result.case.case_id == "normal_01"
    assert [child.result_id for child in run.results] == [result.result_id]
    assert [child.result_id for child in case.results] == [result.result_id]


def test_eval_result_unique_per_run_and_case(session):
    seed_eval_cases(session)
    run = EvalRun(config={"model": "test"})
    session.add(run)
    session.flush()
    session.add(EvalResult(run_id=run.run_id, case_id="normal_01", actual_outcome="submitted", passed=True))
    session.commit()
    session.add(EvalResult(run_id=run.run_id, case_id="normal_01", actual_outcome="submitted", passed=False))
    with pytest.raises(IntegrityError):
        session.commit()


def test_run_aggregates_default_to_null(session):
    run = EvalRun(config={"model": "test"})
    session.add(run)
    session.commit()
    session.refresh(run)
    assert run.success_rate is None
    assert run.field_accuracy is None
    assert run.precision_at_k is None
    assert run.growth_delta is None


def test_invalid_category_rejected_by_pydantic():
    with pytest.raises(ValidationError):
        EvalCaseSeed(
            case_id="x",
            category="bogus",
            input=EvalCaseInput(workflow="shukko", instruction="出張申請", fields={}),
            expected_outcome="submitted",
        )


def test_invalid_outcome_rejected_by_pydantic():
    with pytest.raises(ValidationError):
        EvalCaseSeed(
            case_id="x",
            category="normal",
            input=EvalCaseInput(workflow="shukko", instruction="出張申請", fields={}),
            expected_outcome="bogus",
        )
