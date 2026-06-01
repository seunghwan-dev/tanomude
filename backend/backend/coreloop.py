from typing import Literal

from pydantic import BaseModel, Field

from adapter.base import ScreenAdapter
from adapter.types import AssertSpec, KeyStep
from backend.slotfill import FilledKeysequence, Refusal, RequestInput, SlotExtractor, SlotParseError, Step, fill

MAX_REPLAN = 2
ROLLBACK_MAX_NAV = 3
TRIP_INPUT = "trip_input"
ABORTED = "aborted"
TARGET_SCREEN = "submitted"


class CorrectionCandidate(BaseModel):
    screen: str | None = None
    expected: str
    diffs: list[str] = Field(default_factory=list)
    replan_count: int
    bad_data: bool = False


class ExecutionOutcome(BaseModel):
    status: Literal["submitted", "refused", "verify_failed", "rolled_back", "parse_failed"]
    refusal: Refusal | None = None
    trip_id: int | None = None
    trip_created: bool | None = None
    executed_steps: int = 0
    final_screen: str | None = None
    errors: list[str] = Field(default_factory=list)
    bad_data: bool = False
    correction_candidate: CorrectionCandidate | None = None


def auto_approve(filled: FilledKeysequence) -> bool:
    return True


def derive_idempotency_key(request: RequestInput) -> str | None:
    if request.task_id is None:
        return None
    return f"task:{request.task_id}"


def _to_keystep(step: Step) -> KeyStep:
    return KeyStep(type=step.type, target=step.target, value=step.value, key=step.key)


def _drive(adapter: ScreenAdapter, steps: list[Step]) -> ExecutionOutcome:
    executed = 0
    screen = adapter.read_screen()
    for step in steps:
        adapter.send_keys(_to_keystep(step))
        screen = adapter.wait_for_screen()
        executed += 1
        if screen.errors:
            return ExecutionOutcome(
                status="verify_failed", final_screen=screen.screen, errors=screen.errors,
                executed_steps=executed, bad_data=True,
            )

    verdict = adapter.assert_state(AssertSpec(screen=TARGET_SCREEN, trip_saved=True))
    if not verdict.ok:
        return ExecutionOutcome(
            status="verify_failed",
            final_screen=screen.screen,
            executed_steps=executed,
            errors=[f"{diff.kind}:{diff.key}" for diff in verdict.diffs],
        )

    return ExecutionOutcome(
        status="submitted",
        trip_id=screen.trip_id,
        trip_created=screen.trip_created,
        executed_steps=executed,
        final_screen=screen.screen,
    )


def _attempt(adapter: ScreenAdapter, filled: FilledKeysequence) -> ExecutionOutcome:
    adapter.send_keys(KeyStep(type="nav", key="Enter"))
    screen = adapter.wait_for_screen()
    if screen.errors:
        return ExecutionOutcome(status="verify_failed", final_screen=screen.screen, errors=screen.errors)
    return _drive(adapter, filled.steps)


def _recover_to_trip_input(adapter: ScreenAdapter) -> bool:
    adapter.send_keys(KeyStep(type="fkey", key="F3"))
    screen = adapter.wait_for_screen()
    return screen.screen == TRIP_INPUT


def _replan(adapter: ScreenAdapter, filled: FilledKeysequence) -> ExecutionOutcome:
    return _drive(adapter, filled.steps[1:])


def _rollback(adapter: ScreenAdapter, outcome: ExecutionOutcome, replan_count: int) -> ExecutionOutcome:
    candidate = CorrectionCandidate(
        screen=outcome.final_screen,
        expected=TARGET_SCREEN,
        diffs=outcome.errors,
        replan_count=replan_count,
        bad_data=outcome.bad_data,
    )
    screen = adapter.read_screen()
    guard = 0
    while screen.screen != ABORTED and guard < ROLLBACK_MAX_NAV:
        adapter.send_keys(KeyStep(type="fkey", key="F3"))
        screen = adapter.wait_for_screen()
        guard += 1
    return ExecutionOutcome(
        status="rolled_back",
        final_screen=screen.screen,
        executed_steps=outcome.executed_steps,
        errors=outcome.errors,
        correction_candidate=candidate,
    )


def plan(request: RequestInput, slot_fn: SlotExtractor, context: str = "") -> FilledKeysequence | Refusal:
    return fill(request, slot_fn, context)


def execute(
    request: RequestInput,
    filled: FilledKeysequence,
    adapter: ScreenAdapter,
) -> ExecutionOutcome:
    adapter.open(derive_idempotency_key(request))
    try:
        outcome = _attempt(adapter, filled)
        replan_count = 0
        while outcome.status == "verify_failed" and not outcome.bad_data and replan_count < MAX_REPLAN:
            if not _recover_to_trip_input(adapter):
                break
            replan_count += 1
            outcome = _replan(adapter, filled)

        if outcome.status == "verify_failed":
            return _rollback(adapter, outcome, replan_count)
        return outcome
    finally:
        adapter.close()


def run_task(request: RequestInput, adapter: ScreenAdapter, slot_fn: SlotExtractor, context: str = "") -> ExecutionOutcome:
    try:
        result = plan(request, slot_fn, context)
        if isinstance(result, Refusal):
            return ExecutionOutcome(status="refused", refusal=result, executed_steps=0)
        if not auto_approve(result):
            return ExecutionOutcome(status="verify_failed", errors=["not approved"])
        return execute(request, result, adapter)
    except SlotParseError as exc:
        return ExecutionOutcome(status="parse_failed", errors=exc.errors)
