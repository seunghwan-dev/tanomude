from typing import Literal

from pydantic import BaseModel, Field

from adapter.base import ScreenAdapter
from adapter.types import AssertSpec, KeyStep
from backend.slotfill import FilledKeysequence, Refusal, RequestInput, SlotExtractor, Step, fill


class ExecutionOutcome(BaseModel):
    status: Literal["submitted", "refused", "verify_failed"]
    refusal: Refusal | None = None
    trip_id: int | None = None
    executed_steps: int = 0
    final_screen: str | None = None
    errors: list[str] = Field(default_factory=list)


def auto_approve(filled: FilledKeysequence) -> bool:
    return True


def _to_keystep(step: Step) -> KeyStep:
    return KeyStep(type=step.type, target=step.target, value=step.value, key=step.key)


def execute(adapter: ScreenAdapter, filled: FilledKeysequence) -> ExecutionOutcome:
    screen = adapter.send_keys(KeyStep(type="nav", key="Enter"))
    executed = 0
    if screen.errors:
        return ExecutionOutcome(status="verify_failed", final_screen=screen.screen, errors=screen.errors)

    for step in filled.steps:
        screen = adapter.send_keys(_to_keystep(step))
        executed += 1
        if screen.errors:
            return ExecutionOutcome(
                status="verify_failed", final_screen=screen.screen, errors=screen.errors, executed_steps=executed
            )

    verdict = adapter.assert_state(AssertSpec(screen="submitted", trip_saved=True))
    if not verdict.ok:
        return ExecutionOutcome(
            status="verify_failed",
            final_screen=screen.screen,
            executed_steps=executed,
            errors=[f"{diff.kind}:{diff.key}" for diff in verdict.diffs],
        )

    return ExecutionOutcome(
        status="submitted", trip_id=screen.trip_id, executed_steps=executed, final_screen=screen.screen
    )


def run_task(request: RequestInput, adapter: ScreenAdapter, slot_fn: SlotExtractor, context: str = "") -> ExecutionOutcome:
    result = fill(request, slot_fn, context)
    if isinstance(result, Refusal):
        return ExecutionOutcome(status="refused", refusal=result, executed_steps=0)
    if not auto_approve(result):
        return ExecutionOutcome(status="verify_failed", errors=["not approved"])
    return execute(adapter, result)
