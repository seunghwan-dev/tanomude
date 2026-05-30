import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.coreloop import ExecutionOutcome
from backend.models import Execution, Task


def create_task(
    db: Session, workflow: str, instruction: str, fields: dict, dedup_key: str | None, status: str
) -> Task:
    task = Task(workflow=workflow, instruction=instruction, fields=fields, dedup_key=dedup_key, status=status)
    db.add(task)
    db.commit()
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


def fail_execution(db: Session, execution: Execution, task: Task, error_message: str, task_status: str) -> None:
    execution.status = "errored"
    execution.errors = [error_message]
    execution.finished_at = dt.datetime.now(dt.timezone.utc)
    task.status = task_status
    db.commit()
    db.refresh(execution)
    db.refresh(task)


def get_task(db: Session, task_id: int) -> Task | None:
    return db.get(Task, task_id)


def list_tasks(db: Session) -> list[Task]:
    return list(db.scalars(select(Task).order_by(Task.id)))


def list_executions(db: Session, task_id: int) -> list[Execution]:
    return list(
        db.scalars(select(Execution).where(Execution.task_id == task_id).order_by(Execution.attempt_no))
    )
