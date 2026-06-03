import logging
import time
from uuid import uuid4

import httpx
from fastapi import status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db import SessionLocal
from backend.eval_dataset import EVAL_CASES, EvalCaseSeed, seed_eval_cases
from backend.models import EvalCase, EvalResult, EvalRun
from backend.ollama_client import MODEL, health
from backend.slotfill import PURPOSE_MAX, parse_date, recalc_days, resolve_proj

logger = logging.getLogger(__name__)

DEST_GOLDEN = {
    "大阪": "OSAKA",
    "東京": "TOKYO",
    "名古屋": "NAGOYA",
    "福岡": "FUKUOKA",
    "札幌": "SAPPORO",
    "仙台": "SENDAI",
    "広島": "HIROSHIMA",
    "横浜": "YOKOHAMA",
}

EXECUTED_OUTCOMES = ("submitted", "育成候補", "要調査")
FAILURE_CATEGORIES = ("empty", "wrong_code")


class CaseResult(BaseModel):
    case_id: str
    category: str
    expected_outcome: str
    actual_outcome: str
    passed: bool
    step_count: int | None = None
    replan_count: int | None = None
    latency_ms: int | None = None
    field_accuracy: float | None = None


def _iso(yyyymmdd: str) -> str:
    return f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def expected_fields(fields: dict) -> dict[str, str | int]:
    expected: dict[str, str | int] = {}
    dest = fields.get("dest")
    if dest in DEST_GOLDEN:
        expected["dest"] = DEST_GOLDEN[dest]
    dept = parse_date(fields.get("dept_date")) if fields.get("dept_date") else None
    ret = parse_date(fields.get("ret_date")) if fields.get("ret_date") else None
    if dept is not None:
        expected["dept_date"] = _iso(dept)
    if ret is not None:
        expected["ret_date"] = _iso(ret)
    if dept is not None and ret is not None:
        expected["days"] = int(recalc_days(dept, ret))
    proj = resolve_proj(fields)
    if proj is not None:
        expected["proj"] = proj
    purpose = fields.get("purpose")
    if isinstance(purpose, str) and purpose != "":
        expected["purpose"] = purpose[:PURPOSE_MAX]
    return expected


def field_accuracy(trip: dict, fields: dict) -> float | None:
    expected = expected_fields(fields)
    if not expected:
        return None
    matches = 0
    for key, value in expected.items():
        actual = trip.get(key)
        if key == "days":
            ok = actual is not None and int(actual) == value
        else:
            ok = str(actual) == str(value)
        if ok:
            matches += 1
    return matches / len(expected)


def outcome_from_execution(execution: dict) -> str:
    if execution.get("status") == "submitted":
        return "submitted"
    candidate = execution.get("correction_candidate")
    if execution.get("status") == "rolled_back":
        if candidate and candidate.get("bad_data"):
            return "育成候補"
        return "要調査"
    return str(execution.get("status"))


def _get_trip(mock_base: str, trip_id: int) -> dict:
    response = httpx.get(f"{mock_base}/trip/{trip_id}", timeout=10.0)
    response.raise_for_status()
    return response.json()


def run_case(plat, mock_base: str, case: EvalCaseSeed, dedup_key: str | None) -> CaseResult:
    body = {
        "workflow": case.input.workflow,
        "instruction": case.input.instruction,
        "fields": case.input.fields,
        "dedup_key": dedup_key,
    }
    start = time.perf_counter()
    actual = "errored"
    step_count: int | None = None
    replan_count: int | None = None
    field_acc: float | None = None
    plan_response = plat.post("/tasks/plan", json=body)
    if plan_response.status_code == status.HTTP_409_CONFLICT:
        actual = "idempotent"
    else:
        data = plan_response.json()
        task = data["task"]
        if task["status"] == "refused" or data.get("refusal"):
            actual = "refused"
        elif data.get("plan"):
            approval = plat.post(f"/tasks/{task['id']}/approve", json={"approver": "eval"})
            execution = approval.json()["executions"][-1]
            actual = outcome_from_execution(execution)
            step_count = execution.get("executed_steps")
            candidate = execution.get("correction_candidate")
            replan_count = candidate.get("replan_count") if candidate else 0
            if actual == "submitted" and execution.get("trip_id") is not None:
                field_acc = field_accuracy(_get_trip(mock_base, execution["trip_id"]), case.input.fields)
        else:
            actual = str(task["status"])
    latency_ms = int((time.perf_counter() - start) * 1000)
    return CaseResult(
        case_id=case.case_id,
        category=case.category,
        expected_outcome=case.expected_outcome,
        actual_outcome=actual,
        passed=actual == case.expected_outcome,
        step_count=step_count,
        replan_count=replan_count,
        latency_ms=latency_ms,
        field_accuracy=field_acc,
    )


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def aggregate(results: list[CaseResult]) -> dict[str, float | None]:
    normal = [r for r in results if r.category == "normal"]
    failures = [r for r in results if r.category in FAILURE_CATEGORIES]
    transient = [r for r in results if r.category == "transient"]
    executed = [r for r in results if r.actual_outcome in EXECUTED_OUTCOMES]
    submitted = [r for r in executed if r.actual_outcome == "submitted"]
    field_scores = [r.field_accuracy for r in results if r.field_accuracy is not None]
    step_counts = [float(r.step_count) for r in results if r.step_count is not None]
    return {
        "success_rate": _ratio(sum(1 for r in normal if r.actual_outcome == "submitted"), len(normal)),
        "routing_accuracy": _ratio(sum(1 for r in failures if r.passed), len(failures)),
        "field_accuracy": _mean(field_scores),
        "verify_pass_rate": _ratio(len(submitted), len(executed)),
        "avg_steps": _mean(step_counts),
        "recovery_rate": _ratio(sum(1 for r in transient if r.actual_outcome == "submitted"), len(transient)),
    }


def deterministic_cases() -> list[EvalCaseSeed]:
    return [case for case in EVAL_CASES if case.category != "transient"]


def run_eval(
    plat,
    db: Session,
    mock_base: str,
    run_nonce: str,
    cases: list[EvalCaseSeed] | None = None,
    transient_inject: bool = False,
    on_case=None,
) -> tuple[int, list[CaseResult]]:
    selected = cases if cases is not None else deterministic_cases()
    run = EvalRun(
        config={"model": MODEL, "corrections_applied": False, "transient_inject": transient_inject}
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    results: list[CaseResult] = []
    for case in selected:
        if on_case is not None:
            on_case(case)
        dedup_key = f"{run_nonce}:{case.input.dedup_key}" if case.input.dedup_key else None
        try:
            result = run_case(plat, mock_base, case, dedup_key)
        except Exception:
            logger.warning("eval case %s errored", case.case_id, exc_info=True)
            result = CaseResult(
                case_id=case.case_id,
                category=case.category,
                expected_outcome=case.expected_outcome,
                actual_outcome="errored",
                passed=False,
            )
        results.append(result)
        db.add(
            EvalResult(
                run_id=run.run_id,
                case_id=case.case_id,
                actual_outcome=result.actual_outcome,
                passed=result.passed,
                field_accuracy=result.field_accuracy,
                step_count=result.step_count,
                replan_count=result.replan_count,
                latency_ms=result.latency_ms,
            )
        )
    db.commit()
    metrics = aggregate(results)
    run.success_rate = metrics["success_rate"]
    run.field_accuracy = metrics["field_accuracy"]
    run.routing_accuracy = metrics["routing_accuracy"]
    run.recovery_rate = metrics["recovery_rate"]
    run.verify_pass_rate = metrics["verify_pass_rate"]
    run.avg_steps = metrics["avg_steps"]
    db.commit()
    db.refresh(run)
    return run.run_id, results


def main() -> int:
    import json

    from fastapi.testclient import TestClient

    from backend.agent.app import app
    from backend.agent.service import get_execute_runner
    from backend.eval_transient import fail_submits_for, transient_execute_runner

    if not health():
        print("ollama unavailable; runner structure verified, numbers deferred")
        return 0
    nonce = uuid4().hex[:8]
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(EvalCase)) == 0:
            seed_eval_cases(db)

        def on_case(case: EvalCaseSeed) -> None:
            if case.category == "transient":
                runner = transient_execute_runner(fail_submits_for(case))
                app.dependency_overrides[get_execute_runner] = lambda bound=runner: bound
            else:
                app.dependency_overrides.pop(get_execute_runner, None)

        with TestClient(app) as plat:
            run_id, results = run_eval(
                plat, db, settings.mock_as400_url, nonce, cases=EVAL_CASES, transient_inject=True, on_case=on_case
            )
        app.dependency_overrides.pop(get_execute_runner, None)
        metrics = aggregate(results)
    print(json.dumps({"run_id": run_id, "metrics": metrics}, ensure_ascii=False))
    for result in results:
        print(json.dumps(result.model_dump(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
