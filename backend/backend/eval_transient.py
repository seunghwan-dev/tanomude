import httpx

from adapter.base import ScreenAdapter
from adapter.mock_adapter import MockAdapter
from adapter.types import AssertResult, AssertSpec, KeyStep, Screen
from backend.agent.service import ExecuteRunner
from backend.config import settings
from backend.coreloop import MAX_REPLAN, execute
from backend.eval_dataset import EvalCaseSeed

CONFIRM_SCREEN = "confirm"


class TransientAdapter(ScreenAdapter):
    def __init__(self, inner: ScreenAdapter, fail_submits: int):
        self._inner = inner
        self._fail_submits = fail_submits
        self.swallowed = 0

    def open(self, idempotency_key: str | None = None) -> Screen | None:
        return self._inner.open(idempotency_key)

    def close(self) -> None:
        self._inner.close()

    def read_screen(self) -> Screen:
        return self._inner.read_screen()

    def send_keys(self, step: KeyStep) -> Screen:
        if step.key == "Enter" and self.swallowed < self._fail_submits:
            current = self._inner.read_screen()
            if current.screen == CONFIRM_SCREEN:
                self.swallowed += 1
                return current
        return self._inner.send_keys(step)

    def assert_state(self, spec: AssertSpec) -> AssertResult:
        return self._inner.assert_state(spec)


def fail_submits_for(case: EvalCaseSeed) -> int:
    if case.category != "transient":
        return 0
    return 1 if case.expected_outcome == "submitted" else MAX_REPLAN + 1


def transient_execute_runner(fail_submits: int) -> ExecuteRunner:
    def runner(request, filled, observer=None):
        client = httpx.Client(base_url=settings.mock_as400_url)
        try:
            adapter = TransientAdapter(MockAdapter(client), fail_submits=fail_submits)
            return execute(request, filled, adapter, observer=observer)
        finally:
            client.close()

    return runner
