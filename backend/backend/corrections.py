from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import PersonalCorrection

OVERRIDE_HEADER = "【個人教正・最優先（手順書より優先）】"
RAG_HEADER = "【手順書】"


def _trigger_matches(trigger: dict, fields: dict) -> bool:
    return all(key in fields and fields[key] == value for key, value in trigger.items())


def match_corrections(db: Session, workflow: str, fields: dict) -> list[PersonalCorrection]:
    rows = db.scalars(
        select(PersonalCorrection)
        .where(PersonalCorrection.workflow == workflow, PersonalCorrection.status == "active")
        .order_by(PersonalCorrection.id)
    ).all()
    return [row for row in rows if _trigger_matches(row.trigger, fields)]


def apply_corrections(db: Session, workflow: str, fields: dict, base_context: str) -> str:
    matched = match_corrections(db, workflow, fields)
    if not matched:
        return base_context
    corrections = "\n".join(row.correction_text for row in matched)
    return f"{OVERRIDE_HEADER}\n{corrections}\n{RAG_HEADER}\n{base_context}"
