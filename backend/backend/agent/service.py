from collections.abc import Callable

import httpx

from adapter.mock_adapter import MockAdapter
from backend.config import settings
from backend.coreloop import ExecutionOutcome, plan, run_task
from backend.db import SessionLocal
from backend.retrieval import RetrievedChunk, hybrid_search
from backend.slotfill import FilledKeysequence, Refusal, RequestInput, extract_slots, ground

Runner = Callable[[RequestInput], ExecutionOutcome]
PlanRunner = Callable[[RequestInput], tuple[FilledKeysequence | Refusal, list[RetrievedChunk]]]

_ROLLUP = {
    "submitted": "submitted",
    "refused": "refused",
    "verify_failed": "failed",
    "rolled_back": "failed",
    "parse_failed": "failed",
}


def rollup_status(execution_status: str) -> str:
    return _ROLLUP.get(execution_status, "failed")


def _production_runner(request: RequestInput) -> ExecutionOutcome:
    client = httpx.Client(base_url=settings.mock_as400_url)
    try:
        with SessionLocal() as db:
            context = ground(db, request.instruction)
        return run_task(request, MockAdapter(client), extract_slots, context)
    finally:
        client.close()


def get_runner() -> Runner:
    return _production_runner


def _production_plan_runner(
    request: RequestInput,
) -> tuple[FilledKeysequence | Refusal, list[RetrievedChunk]]:
    with SessionLocal() as db:
        grounds = hybrid_search(db, request.instruction)
    context = "\n\n".join(chunk.text for chunk in grounds)
    result = plan(request, extract_slots, context)
    return result, grounds


def get_plan_runner() -> PlanRunner:
    return _production_plan_runner
