from collections.abc import Callable

from backend.agent.manager import manager
from backend.agent.schemas import TaskStepView
from backend.coreloop import StepObserver, StepRecord
from backend.db import SessionLocal
from backend.models import TaskStep

_FIELD_LABELS = {
    "DEST": "目的地コード",
    "DEPTDATE": "出発日",
    "RETDATE": "帰着日",
    "DAYS": "日数",
    "PURPOSE": "目的",
    "PROJ": "案件コード",
    "OVRSEA": "海外区分",
}
_KEY_LABELS = {
    "F4": "案件コード選択",
    "F9": "前回案件コード再利用",
    "F3": "中断",
    "Tab": "フィールド移動",
    "FieldExit": "フィールド移動",
    "Enter": "確定",
}


def derive_intent(action: dict) -> str:
    step_type = action.get("type")
    if step_type == "field":
        target = action.get("target")
        return f"{_FIELD_LABELS.get(target, target)}入力"
    if step_type == "nav":
        return "画面遷移"
    if step_type == "fkey":
        return _KEY_LABELS.get(action.get("key"), action.get("key") or "操作")
    return "操作"


StepEmit = Callable[[str, int, dict], None]


def build_step_observer(execution_id: int, task_id: int, emit: StepEmit | None = None) -> StepObserver:
    send = emit if emit is not None else manager.emit_threadsafe
    ordinal = 0

    def observe(record: StepRecord) -> None:
        nonlocal ordinal
        ordinal += 1
        with SessionLocal() as db:
            step = TaskStep(
                task_id=task_id,
                execution_id=execution_id,
                ordinal=ordinal,
                intent=derive_intent(record.action),
                action=record.action,
                screen=record.screen,
                screen_fields=record.screen_fields,
                status=record.status,
                errors=record.errors,
            )
            db.add(step)
            db.commit()
            db.refresh(step)
            payload = TaskStepView.model_validate(step).model_dump(mode="json")
        send("step_executed", task_id, payload)

    return observe
