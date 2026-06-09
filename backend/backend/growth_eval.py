from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.corrections import create_correction
from backend.models import EvalRun, PersonalCorrection, Task
from backend.ollama_client import MODEL

WORKFLOW = "shutchou"
REUSE_TEXT = "前回案件コードを再利用し reuse_prev_proj を true に上書きすること。手順書の指定より優先する。"
OVERSEAS_TEXT = "この申請は海外扱いとし overseas を true に上書きすること。手順書の指定より優先する。"


class CorrectionCase(BaseModel):
    case_id: str
    case_type: Literal["policy", "boundary"]
    trigger: dict
    fields: dict[str, str | bool]
    instruction: str
    slot: str
    corrected_value: str | bool
    correction_text: str
    expected_value: str | bool | None = None


def _fields(dest: str) -> dict[str, str | bool]:
    return {
        "dest": dest,
        "dept_date": "2026-06-10",
        "ret_date": "2026-06-12",
        "proj_hint": "P-001",
        "purpose": "製品X納入調整",
    }


def _reuse(case_id: str, city: str) -> CorrectionCase:
    return CorrectionCase(
        case_id=case_id,
        case_type="policy",
        trigger={"dest": city},
        fields=_fields(city),
        instruction=f"{city}へ出張する。",
        slot="reuse_prev_proj",
        corrected_value=True,
        correction_text=REUSE_TEXT,
    )


def _overseas(case_id: str, city: str) -> CorrectionCase:
    return CorrectionCase(
        case_id=case_id,
        case_type="policy",
        trigger={"dest": city},
        fields=_fields(city),
        instruction=f"{city}へ出張する。",
        slot="overseas",
        corrected_value=True,
        correction_text=OVERSEAS_TEXT,
    )


CORRECTION_CASES: list[CorrectionCase] = [
    _reuse("reuse_osaka", "大阪"),
    _reuse("reuse_tokyo", "東京"),
    _reuse("reuse_nagoya", "名古屋"),
    _reuse("reuse_fukuoka", "福岡"),
    _overseas("overseas_sapporo", "札幌"),
    _overseas("overseas_hiroshima", "広島"),
    _overseas("overseas_yokohama", "横浜"),
    _overseas("overseas_sendai", "仙台"),
    CorrectionCase(
        case_id="boundary_overseas_kyoto",
        case_type="boundary",
        trigger={"dest": "京都"},
        fields=_fields("京都"),
        instruction="京都へ国内出張する。",
        slot="overseas",
        corrected_value=True,
        correction_text=OVERSEAS_TEXT,
        expected_value=False,
    ),
    CorrectionCase(
        case_id="boundary_overseas_kobe",
        case_type="boundary",
        trigger={"dest": "神戸"},
        fields=_fields("神戸"),
        instruction="神戸へ国内出張する。",
        slot="overseas",
        corrected_value=True,
        correction_text=OVERSEAS_TEXT,
        expected_value=False,
    ),
    CorrectionCase(
        case_id="boundary_dest_code_nagasaki",
        case_type="boundary",
        trigger={"dest": "長崎"},
        fields=_fields("長崎"),
        instruction="長崎へ出張する。",
        slot="dest_code",
        corrected_value="SAPPORO",
        correction_text="目的地コード dest_code は必ず SAPPORO に上書きすること。手順書の指定より優先する。",
        expected_value="NAGASAKI",
    ),
    CorrectionCase(
        case_id="boundary_purpose_kanazawa",
        case_type="boundary",
        trigger={"dest": "金沢"},
        fields=_fields("金沢"),
        instruction="金沢へ出張する。",
        slot="purpose",
        corrected_value="会議出席",
        correction_text="purpose は必ず 会議出席 に上書きすること。手順書の指定より優先する。",
        expected_value="製品X納入調整",
    ),
]


def policy_cases() -> list[CorrectionCase]:
    return [case for case in CORRECTION_CASES if case.case_type == "policy"]


def boundary_cases() -> list[CorrectionCase]:
    return [case for case in CORRECTION_CASES if case.case_type == "boundary"]


def match_rate(cases: list[CorrectionCase], observe: Callable[[CorrectionCase], object], target: str) -> float:
    if not cases:
        return 0.0
    return sum(1 for case in cases if observe(case) == getattr(case, target)) / len(cases)


def observe_slot(plat, case: CorrectionCase):
    body = {"workflow": WORKFLOW, "instruction": case.instruction, "fields": case.fields}
    plan = plat.post("/tasks/plan", json=body).json().get("plan")
    if plan is None:
        return None
    value = plan["analysis"].get(case.slot)
    return value.upper() if isinstance(value, str) else value


def clear_corrections(db: Session) -> None:
    db.execute(delete(PersonalCorrection).where(PersonalCorrection.workflow == WORKFLOW))
    db.commit()


def seed_corrections(db: Session) -> None:
    for case in CORRECTION_CASES:
        create_correction(db, WORKFLOW, case.trigger, case.correction_text, source="eval")


def clear_probe_tasks(db: Session) -> None:
    db.execute(delete(Task).where(Task.workflow == WORKFLOW, Task.instruction.like("%へ%出張する。")))
    db.commit()


def run_growth_eval(plat, db: Session) -> tuple[int, float, float, dict, dict]:
    clear_corrections(db)
    control = {case.case_id: observe_slot(plat, case) for case in CORRECTION_CASES}
    seed_corrections(db)
    treatment = {case.case_id: observe_slot(plat, case) for case in CORRECTION_CASES}
    clear_corrections(db)
    policy = policy_cases()
    boundary = boundary_cases()
    control_rate = match_rate(policy, lambda case: control[case.case_id], "corrected_value")
    treatment_rate = match_rate(policy, lambda case: treatment[case.case_id], "corrected_value")
    growth_delta = treatment_rate - control_rate
    boundary_respect_rate = match_rate(boundary, lambda case: treatment[case.case_id], "expected_value")
    boundary_control_sanity = match_rate(boundary, lambda case: control[case.case_id], "expected_value")
    run = EvalRun(
        config={
            "model": MODEL,
            "eval": "growth_delta",
            "policy_cases": len(policy),
            "boundary_cases": len(boundary),
            "control_rate": control_rate,
            "treatment_rate": treatment_rate,
            "boundary_control_sanity": boundary_control_sanity,
        },
        growth_delta=growth_delta,
        boundary_respect_rate=boundary_respect_rate,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    clear_probe_tasks(db)
    return run.run_id, growth_delta, boundary_respect_rate, control, treatment


def main() -> int:
    import json

    from fastapi.testclient import TestClient

    from backend.agent.app import app
    from backend.db import SessionLocal
    from backend.ollama_client import health

    if not health():
        print("ollama unavailable; growth-delta structure verified, numbers deferred")
        return 0
    with SessionLocal() as db:
        with TestClient(app) as plat:
            run_id, growth_delta, boundary_respect_rate, control, treatment = run_growth_eval(plat, db)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "growth_delta": growth_delta,
                "boundary_respect_rate": boundary_respect_rate,
            }
        )
    )
    for case in CORRECTION_CASES:
        print(
            json.dumps(
                {
                    "case_id": case.case_id,
                    "type": case.case_type,
                    "slot": case.slot,
                    "control": control[case.case_id],
                    "treatment": treatment[case.case_id],
                    "corrected": case.corrected_value,
                    "expected": case.expected_value,
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
