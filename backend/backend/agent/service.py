from collections.abc import Callable

import httpx
from pydantic import BaseModel

from adapter.mock_adapter import MockAdapter
from backend.config import settings
from backend.coreloop import ExecutionOutcome, StepObserver, execute, plan, run_task
from backend.corrections import apply_corrections
from backend.db import SessionLocal
from backend.retrieval import RetrievedChunk, hybrid_search
from backend.slotfill import (
    FilledKeysequence,
    Refusal,
    RequestInput,
    SlotParseError,
    extract_slots,
    ground,
    immune_extractor,
)


class ParseFailure(BaseModel):
    errors: list[str]


Runner = Callable[[RequestInput, StepObserver | None], ExecutionOutcome]
ExecuteRunner = Callable[[RequestInput, FilledKeysequence, StepObserver | None], ExecutionOutcome]
PlanRunner = Callable[
    [RequestInput], tuple[FilledKeysequence | Refusal | ParseFailure, list[RetrievedChunk]]
]

_ROLLUP = {
    "submitted": "submitted",
    "refused": "refused",
    "verify_failed": "failed",
    "rolled_back": "failed",
    "parse_failed": "failed",
}


def rollup_status(execution_status: str) -> str:
    return _ROLLUP.get(execution_status, "failed")


def _production_runner(request: RequestInput, observer: StepObserver | None = None) -> ExecutionOutcome:
    client = httpx.Client(base_url=settings.mock_as400_url)
    try:
        with SessionLocal() as db:
            context = ground(db, request.instruction)
        return run_task(request, MockAdapter(client), extract_slots, context, observer=observer)
    finally:
        client.close()


def get_runner() -> Runner:
    return _production_runner


def _production_execute_runner(
    request: RequestInput, filled: FilledKeysequence, observer: StepObserver | None = None
) -> ExecutionOutcome:
    client = httpx.Client(base_url=settings.mock_as400_url)
    try:
        return execute(request, filled, MockAdapter(client), observer=observer)
    finally:
        client.close()


def get_execute_runner() -> ExecuteRunner:
    return _production_execute_runner


def _production_plan_runner(
    request: RequestInput,
) -> tuple[FilledKeysequence | Refusal | ParseFailure, list[RetrievedChunk]]:
    with SessionLocal() as db:
        grounds = hybrid_search(db, request.instruction)
        rag_context = "\n\n".join(chunk.text for chunk in grounds)
        context, _fallback = apply_corrections(db, request.workflow, request.fields, rag_context)
    try:
        result = plan(request, immune_extractor(rag_context), context)
    except SlotParseError as exc:
        return ParseFailure(errors=exc.errors), grounds
    return result, grounds


def get_plan_runner() -> PlanRunner:
    return _production_plan_runner
