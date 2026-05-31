from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.agent import repository
from backend.agent.manager import manager
from backend.agent.schemas import ExecutionView, PlanView, RefusalView, TaskCreate, TaskPlanView, TaskView
from backend.agent.service import PlanRunner, Runner, get_plan_runner, get_runner, rollup_status
from backend.db import get_db
from backend.models import Execution, Task
from backend.slotfill import Refusal, RequestInput

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
    await manager.broadcast("task_created", task.id, {"status": task.status})
    execution = repository.create_execution(db, task.id, attempt_no=1, status="running")
    await manager.broadcast(
        "execution_started",
        task.id,
        {"execution_id": execution.id, "attempt_no": execution.attempt_no, "status": execution.status},
    )
    request = RequestInput(
        workflow=body.workflow, instruction=body.instruction, fields=body.fields, task_id=str(task.id)
    )
    try:
        outcome = await to_thread.run_sync(runner, request)
    except Exception as exc:
        repository.fail_execution(db, execution, task, repr(exc), rollup_status("errored"))
        await manager.broadcast(
            "execution_finished", task.id, {"execution_id": execution.id, "status": execution.status}
        )
        await manager.broadcast("status_changed", task.id, {"status": task.status})
        raise
    repository.finalize_execution(db, execution, task, outcome, rollup_status(outcome.status))
    await manager.broadcast(
        "execution_finished",
        task.id,
        {
            "execution_id": execution.id,
            "status": execution.status,
            "trip_id": execution.trip_id,
            "trip_created": execution.trip_created,
        },
    )
    await manager.broadcast("status_changed", task.id, {"status": task.status})
    return _to_view(task, repository.list_executions(db, task.id))


@router.post("/plan", response_model=TaskPlanView, status_code=status.HTTP_201_CREATED)
async def create_plan_task(
    body: TaskCreate, db: Session = Depends(get_db), plan_runner: PlanRunner = Depends(get_plan_runner)
) -> TaskPlanView:
    task = repository.create_task(
        db, body.workflow, body.instruction, body.fields, body.dedup_key, status="awaiting_approval"
    )
    await manager.broadcast("task_created", task.id, {"status": task.status})
    request = RequestInput(
        workflow=body.workflow, instruction=body.instruction, fields=body.fields, task_id=str(task.id)
    )
    try:
        result, grounds = await to_thread.run_sync(plan_runner, request)
    except Exception:
        repository.set_task_status(db, task, "errored")
        await manager.broadcast("status_changed", task.id, {"status": task.status})
        raise
    if isinstance(result, Refusal):
        repository.set_task_status(db, task, "refused")
        await manager.broadcast(
            "status_changed", task.id, {"status": task.status, "reason": result.reason}
        )
        return TaskPlanView(
            task=_to_view(task, []),
            refusal=RefusalView(reason=result.reason, missing_fields=result.missing_fields),
        )
    plan = repository.create_plan(
        db,
        task.id,
        analysis=result.slots.model_dump(),
        keysequence=[step.model_dump() for step in result.steps],
        grounding=[chunk.model_dump() for chunk in grounds],
    )
    plan_view = PlanView.model_validate(plan)
    await manager.broadcast("plan_ready", task.id, plan_view.model_dump(mode="json"))
    return TaskPlanView(task=_to_view(task, []), plan=plan_view)


@router.get("", response_model=list[TaskView])
def list_tasks(db: Session = Depends(get_db)) -> list[TaskView]:
    return [_to_view(task, repository.list_executions(db, task.id)) for task in repository.list_tasks(db)]


@router.get("/{task_id}", response_model=TaskView)
def get_task(task_id: int, db: Session = Depends(get_db)) -> TaskView:
    task = repository.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    return _to_view(task, repository.list_executions(db, task.id))
