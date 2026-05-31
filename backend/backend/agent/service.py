from collections.abc import Callable

import httpx

from adapter.mock_adapter import MockAdapter
from backend.config import settings
from backend.coreloop import ExecutionOutcome, run_task
from backend.db import SessionLocal
from backend.slotfill import RequestInput, extract_slots, ground

Runner = Callable[[RequestInput], ExecutionOutcome]

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
