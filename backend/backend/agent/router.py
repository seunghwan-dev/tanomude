from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.agent import repository
from backend.agent.schemas import ExecutionView, TaskCreate, TaskView
from backend.agent.service import Runner, get_runner, rollup_status
from backend.db import get_db
from backend.models import Execution, Task
from backend.slotfill import RequestInput

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _to_view(task: Task, executions: list[Execution]) -> TaskView:
    return TaskView(
        id=task.id,
        dedup_key=task.dedup_key,
        workflow=task.workflow,
        instruction=task.instruction,
        fields=task.fields,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        executions=[ExecutionView.model_validate(execution) for execution in executions],
    )


@router.post("", response_model=TaskView, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate, db: Session = Depends(get_db), runner: Runner = Depends(get_runner)
) -> TaskView:
    task = repository.create_task(
        db, body.workflow, body.instruction, body.fields, body.dedup_key, status="running"
    )
    execution = repository.create_execution(db, task.id, attempt_no=1, status="running")
    request = RequestInput(
        workflow=body.workflow, instruction=body.instruction, fields=body.fields, task_id=body.dedup_key
    )
    outcome = await to_thread.run_sync(runner, request)
    repository.finalize_execution(db, execution, task, outcome, rollup_status(outcome.status))
    return _to_view(task, repository.list_executions(db, task.id))


@router.get("", response_model=list[TaskView])
def list_tasks(db: Session = Depends(get_db)) -> list[TaskView]:
    return [_to_view(task, repository.list_executions(db, task.id)) for task in repository.list_tasks(db)]


@router.get("/{task_id}", response_model=TaskView)
def get_task(task_id: int, db: Session = Depends(get_db)) -> TaskView:
    task = repository.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    return _to_view(task, repository.list_executions(db, task.id))
