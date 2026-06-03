import datetime as dt

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.coreloop import ExecutionOutcome
from backend.models import Approval, AuditLog, Execution, Plan, Task


class DuplicateDedupKey(Exception):
    def __init__(self, existing: Task) -> None:
        self.existing = existing


def get_task_by_dedup_key(db: Session, dedup_key: str | None) -> Task | None:
    if dedup_key is None:
        return None
    return db.scalars(select(Task).where(Task.dedup_key == dedup_key)).first()


def create_task(
    db: Session, workflow: str, instruction: str, fields: dict, dedup_key: str | None, status: str
) -> Task:
    task = Task(workflow=workflow, instruction=instruction, fields=fields, dedup_key=dedup_key, status=status)
    db.add(task)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = get_task_by_dedup_key(db, dedup_key)
        if existing is None:
            raise
        raise DuplicateDedupKey(existing) from exc
    db.refresh(task)
    return task


def create_execution(db: Session, task_id: int, attempt_no: int, status: str) -> Execution:
    execution = Execution(task_id=task_id, attempt_no=attempt_no, status=status, executed_steps=0)
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def finalize_execution(
    db: Session, execution: Execution, task: Task, outcome: ExecutionOutcome, task_status: str
) -> None:
    execution.status = outcome.status
    execution.final_screen = outcome.final_screen
    execution.trip_id = outcome.trip_id
    execution.trip_created = outcome.trip_created
    execution.executed_steps = outcome.executed_steps
    execution.errors = outcome.errors
    execution.correction_candidate = (
        outcome.correction_candidate.model_dump() if outcome.correction_candidate is not None else None
    )
    execution.finished_at = dt.datetime.now(dt.timezone.utc)
    task.status = task_status
    db.commit()
    db.refresh(execution)
    db.refresh(task)


def set_task_status(db: Session, task: Task, status: str) -> None:
    task.status = status
    db.commit()
    db.refresh(task)


def create_plan(
    db: Session,
    task_id: int,
    analysis: dict,
    keysequence: list,
    grounding: list,
    version: int = 1,
    status: str = "proposed",
) -> Plan:
    plan = Plan(
        task_id=task_id,
        version=version,
        analysis=analysis,
        keysequence=keysequence,
        grounding=grounding,
        status=status,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def fail_execution(db: Session, execution: Execution, task: Task, error_message: str, task_status: str) -> None:
    execution.status = "errored"
    execution.errors = [error_message]
    execution.finished_at = dt.datetime.now(dt.timezone.utc)
    task.status = task_status
    db.commit()
    db.refresh(execution)
    db.refresh(task)


def get_plan(db: Session, task_id: int) -> Plan | None:
    return db.scalars(
        select(Plan).where(Plan.task_id == task_id, Plan.status == "proposed").order_by(Plan.version.desc())
    ).first()


def _stage_decision(
    db: Session, task: Task, plan_id: int, decision: str, approver: str, decision_text: str | None
) -> None:
    db.add(
        Approval(
            task_id=task.id, plan_id=plan_id, decision=decision, approver=approver, decision_text=decision_text
        )
    )
    db.add(
        AuditLog(
            task_id=task.id, plan_id=plan_id, approver=approver, decision=decision, decision_text=decision_text
        )
    )


def record_reject(db: Session, task: Task, plan_id: int, approver: str, decision_text: str | None) -> None:
    _stage_decision(db, task, plan_id, "reject", approver, decision_text)
    task.status = "refused"
    db.commit()
    db.refresh(task)


def record_revise(db: Session, task: Task, plan_id: int, approver: str, decision_text: str | None) -> None:
    _stage_decision(db, task, plan_id, "revise", approver, decision_text)
    db.commit()
    db.refresh(task)


def record_approve(
    db: Session, task: Task, plan_id: int, approver: str, decision_text: str | None
) -> Execution:
    _stage_decision(db, task, plan_id, "approve", approver, decision_text)
    task.status = "running"
    execution = Execution(task_id=task.id, attempt_no=1, status="running", executed_steps=0)
    db.add(execution)
    db.commit()
    db.refresh(task)
    db.refresh(execution)
    return execution


def get_task(db: Session, task_id: int) -> Task | None:
    return db.get(Task, task_id)


def list_tasks(db: Session) -> list[Task]:
    return list(db.scalars(select(Task).order_by(Task.id)))


def list_executions(db: Session, task_id: int) -> list[Execution]:
    return list(
        db.scalars(
            select(Execution)
            .where(Execution.task_id == task_id)
            .order_by(Execution.attempt_no)
            .options(selectinload(Execution.steps))
        )
    )
