import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend import growth_eval, ollama_client
from backend.agent.app import app
from backend.db import SessionLocal
from backend.growth_eval import (
    CORRECTION_CASES,
    boundary_cases,
    match_rate,
    policy_cases,
    run_growth_eval,
)
from backend.models import EvalRun, PersonalCorrection, Task

requires_ollama = pytest.mark.skipif(not ollama_client.health(), reason="ollama not reachable")


def test_set_composition():
    assert len(CORRECTION_CASES) == 12
    assert len(policy_cases()) == 8
    assert len(boundary_cases()) == 4
    cities = [case.trigger["dest"] for case in CORRECTION_CASES]
    assert len(set(cities)) == 12


def test_growth_delta_formula_perfect():
    policy = policy_cases()
    control = match_rate(policy, lambda case: not case.corrected_value, "corrected_value")
    treatment = match_rate(policy, lambda case: case.corrected_value, "corrected_value")
    assert control == 0.0
    assert treatment == 1.0
    assert treatment - control == 1.0


def test_growth_delta_below_one_when_one_policy_does_not_flip():
    policy = policy_cases()
    stuck = policy[0].case_id

    def observe(case):
        return (not case.corrected_value) if case.case_id == stuck else case.corrected_value

    treatment = match_rate(policy, observe, "corrected_value")
    assert treatment == pytest.approx(7 / 8)
    assert treatment - 0.0 < 1.0


def test_boundary_respect_rate_formula_perfect():
    boundary = boundary_cases()
    assert match_rate(boundary, lambda case: case.expected_value, "expected_value") == 1.0


def test_boundary_respect_rate_below_one_when_one_boundary_flips():
    boundary = boundary_cases()
    breached = boundary[0].case_id

    def observe(case):
        return case.corrected_value if case.case_id == breached else case.expected_value

    assert match_rate(boundary, observe, "expected_value") == pytest.approx(3 / 4)


@pytest.fixture
def growth_env():
    client = TestClient(app)
    try:
        yield client
    finally:
        with SessionLocal() as session:
            session.execute(delete(PersonalCorrection).where(PersonalCorrection.workflow == "shutchou"))
            session.execute(delete(Task).where(Task.workflow == "shutchou", Task.instruction.like("%へ%出張する。")))
            session.commit()


@requires_ollama
def test_run_growth_eval_policy_flips_boundary_respects(growth_env):
    with SessionLocal() as db:
        run_id, growth_delta, boundary_respect_rate, control, treatment = run_growth_eval(growth_env, db)
        run = db.get(EvalRun, run_id)
        assert run.growth_delta == growth_delta
        assert run.boundary_respect_rate == boundary_respect_rate
        leaked = db.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.workflow == "shutchou", Task.instruction.like("%へ%出張する。"))
        )
        assert leaked == 0
        db.delete(run)
        db.commit()
    assert growth_delta >= 0.75
    assert boundary_respect_rate >= 0.5


@requires_ollama
def test_growth_delta_collapses_without_seed(growth_env, monkeypatch):
    monkeypatch.setattr(growth_eval, "seed_corrections", lambda db: None)
    with SessionLocal() as db:
        run_id, growth_delta, boundary_respect_rate, control, treatment = run_growth_eval(growth_env, db)
        db.delete(db.get(EvalRun, run_id))
        db.commit()
    assert growth_delta == 0.0
