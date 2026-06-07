from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import PersonalCorrection

OVERRIDE_HEADER = "【個人修正・最優先（手順書より優先）】"
RAG_HEADER = "【手順書】"
MAX_CORRECTION_LENGTH = 2000


class ExcludedCorrection(NamedTuple):
    id: int
    reason: str


def _trigger_matches(trigger: dict, fields: dict) -> bool:
    return all(key in fields and fields[key] == value for key, value in trigger.items())


def match_corrections(db: Session, workflow: str, fields: dict) -> list[PersonalCorrection]:
    rows = db.scalars(
        select(PersonalCorrection)
        .where(PersonalCorrection.workflow == workflow, PersonalCorrection.status == "active")
        .order_by(PersonalCorrection.id)
    ).all()
    return [row for row in rows if _trigger_matches(row.trigger, fields)]


def _has_control_chars(text: str) -> bool:
    return any(
        ch not in "\t\n\r" and (ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F) for ch in text
    )


def _length_or_control_reason(text: str) -> str | None:
    if len(text) > MAX_CORRECTION_LENGTH:
        return "too_long"
    if _has_control_chars(text):
        return "non_printable"
    return None


def _validation_reason(correction: PersonalCorrection) -> str | None:
    text = correction.correction_text
    if not text.strip():
        return "empty"
    return _length_or_control_reason(text)


def validate_correction(correction: PersonalCorrection) -> bool:
    return _validation_reason(correction) is None


def decision_text_rejection_reason(text: str | None) -> str | None:
    if text is None:
        return None
    return _length_or_control_reason(text)


def apply_corrections(
    db: Session, workflow: str, fields: dict, base_context: str
) -> tuple[str, list[ExcludedCorrection]]:
    matched = match_corrections(db, workflow, fields)
    valid = []
    fallback = []
    for row in matched:
        reason = _validation_reason(row)
        if reason is None:
            valid.append(row)
        else:
            fallback.append(ExcludedCorrection(id=row.id, reason=reason))
    if not valid:
        return base_context, fallback
    corrections = "\n".join(row.correction_text for row in valid)
    context = f"{OVERRIDE_HEADER}\n{corrections}\n{RAG_HEADER}\n{base_context}"
    return context, fallback


def stage_correction(
    db: Session,
    workflow: str,
    trigger: dict,
    correction_text: str,
    source: str,
    approver: str | None = None,
) -> PersonalCorrection:
    existing = db.scalars(
        select(PersonalCorrection).where(
            PersonalCorrection.workflow == workflow,
            PersonalCorrection.status == "active",
            PersonalCorrection.trigger == trigger,
        )
    ).first()
    if existing is not None:
        existing.status = "superseded"
        version = existing.version + 1
        supersedes_id = existing.id
        db.flush()
    else:
        version = 1
        supersedes_id = None
    correction = PersonalCorrection(
        workflow=workflow,
        trigger=trigger,
        correction_text=correction_text,
        status="active",
        version=version,
        supersedes_id=supersedes_id,
        source=source,
        approver=approver,
    )
    db.add(correction)
    return correction


def create_correction(
    db: Session,
    workflow: str,
    trigger: dict,
    correction_text: str,
    source: str,
    approver: str | None = None,
) -> PersonalCorrection:
    correction = stage_correction(db, workflow, trigger, correction_text, source, approver)
    db.commit()
    db.refresh(correction)
    return correction


def deactivate_correction(db: Session, correction_id: int) -> PersonalCorrection:
    correction = db.get(PersonalCorrection, correction_id)
    correction.status = "retired"
    db.commit()
    db.refresh(correction)
    return correction


def quarantine_correction(db: Session, correction_id: int) -> PersonalCorrection:
    correction = db.get(PersonalCorrection, correction_id)
    correction.status = "quarantined"
    db.commit()
    db.refresh(correction)
    return correction
