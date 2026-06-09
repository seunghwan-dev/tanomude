from typing import Literal

from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.models import EvalCase

EvalCategory = Literal["normal", "empty", "wrong_code", "transient", "duplicate"]
EvalOutcome = Literal["submitted", "再入力/コード確認", "要調査", "refused", "idempotent"]


class EvalCaseInput(BaseModel):
    workflow: str
    instruction: str
    fields: dict[str, str | bool]
    dedup_key: str | None = None


class EvalCaseSeed(BaseModel):
    case_id: str
    category: EvalCategory
    input: EvalCaseInput
    expected_outcome: EvalOutcome
    expected_docs: list[str] | None = None


def _fields(dest: str, proj: str, dept: str, ret: str, purpose: str, **extra) -> dict[str, str | bool]:
    base: dict[str, str | bool] = {
        "dest": dest,
        "dept_date": dept,
        "ret_date": ret,
        "proj_hint": proj,
        "purpose": purpose,
    }
    base.update(extra)
    return base


def _case(
    case_id: str,
    category: EvalCategory,
    fields: dict[str, str | bool],
    expected_outcome: EvalOutcome,
    dedup_key: str | None = None,
) -> EvalCaseSeed:
    return EvalCaseSeed(
        case_id=case_id,
        category=category,
        input=EvalCaseInput(
            workflow="shutchou", instruction="出張申請", fields=fields, dedup_key=dedup_key
        ),
        expected_outcome=expected_outcome,
    )


EVAL_CASES: list[EvalCaseSeed] = [
    _case("normal_01", "normal", _fields("大阪", "P-001", "2026-06-10", "2026-06-11", "製品X納入調整"), "submitted"),
    _case("normal_02", "normal", _fields("東京", "P-014", "2026-07-01", "2026-07-03", "定例会議出席"), "submitted"),
    _case("normal_03", "normal", _fields("名古屋", "P-205", "2026-06-18", "2026-06-19", "ABC商事打合せ"), "submitted"),
    _case("normal_04", "normal", _fields("福岡", "P-330", "2026-08-05", "2026-08-08", "実験機A検収"), "submitted"),
    _case("normal_05", "normal", _fields("札幌", "P-072", "2026-09-12", "2026-09-14", "工程監査"), "submitted"),
    _case("normal_06", "normal", _fields("仙台", "P-118", "2026-06-22", "2026-06-22", "据付立会い"), "submitted"),
    _case("normal_07", "normal", _fields("広島", "P-256", "2026-07-15", "2026-07-17", "製品X保守点検"), "submitted"),
    _case("normal_08", "normal", _fields("横浜", "P-049", "2026-10-01", "2026-10-02", "Material-X調達協議", overseas=False), "submitted"),
    _case("empty_01_dest", "empty", _fields("", "P-101", "2026-06-10", "2026-06-11", "製品X納入調整"), "refused"),
    _case("empty_02_retdate", "empty", _fields("大阪", "P-102", "2026-06-10", "", "定例会議出席"), "refused"),
    _case("empty_03_purpose", "empty", _fields("東京", "P-103", "2026-06-10", "2026-06-11", ""), "refused"),
    _case("empty_04_proj", "empty", _fields("名古屋", "", "2026-06-10", "2026-06-11", "工程監査"), "refused"),
    _case("wrong_01_px", "wrong_code", _fields("大阪", "PX-001", "2026-06-10", "2026-06-11", "製品X納入調整"), "再入力/コード確認"),
    _case("wrong_02_short", "wrong_code", _fields("東京", "P-1", "2026-06-10", "2026-06-11", "定例会議出席"), "再入力/コード確認"),
    _case("wrong_03_long", "wrong_code", _fields("名古屋", "P-0001", "2026-06-10", "2026-06-11", "ABC商事打合せ"), "再入力/コード確認"),
    _case("wrong_04_alpha", "wrong_code", _fields("福岡", "ABCDEF", "2026-06-10", "2026-06-11", "実験機A検収"), "再入力/コード確認"),
    _case("transient_recover_01", "transient", _fields("広島", "P-256", "2026-07-15", "2026-07-17", "製品X保守点検"), "submitted"),
    _case("transient_recover_02", "transient", _fields("横浜", "P-049", "2026-08-01", "2026-08-02", "Material-X調達協議"), "submitted"),
    _case("transient_exhaust_01", "transient", _fields("札幌", "P-072", "2026-09-12", "2026-09-14", "工程監査"), "要調査"),
    _case("transient_exhaust_02", "transient", _fields("仙台", "P-118", "2026-06-22", "2026-06-23", "据付立会い"), "要調査"),
    _case("dup_first_01", "duplicate", _fields("大阪", "P-001", "2026-06-10", "2026-06-11", "製品X納入調整"), "submitted", dedup_key="eval:dup:1"),
    _case("dup_second_01", "duplicate", _fields("大阪", "P-001", "2026-06-10", "2026-06-11", "製品X納入調整"), "idempotent", dedup_key="eval:dup:1"),
    _case("dup_first_02", "duplicate", _fields("東京", "P-014", "2026-07-01", "2026-07-03", "定例会議出席"), "submitted", dedup_key="eval:dup:2"),
    _case("dup_second_02", "duplicate", _fields("東京", "P-014", "2026-07-01", "2026-07-03", "定例会議出席"), "idempotent", dedup_key="eval:dup:2"),
]


def seed_eval_cases(db: Session) -> int:
    db.execute(delete(EvalCase))
    db.flush()
    for case in EVAL_CASES:
        db.add(
            EvalCase(
                case_id=case.case_id,
                category=case.category,
                input=case.input.model_dump(),
                expected_outcome=case.expected_outcome,
                expected_docs=case.expected_docs,
            )
        )
    db.commit()
    return len(EVAL_CASES)
