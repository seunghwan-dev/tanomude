import time
from abc import ABC, abstractmethod

from adapter.types import AssertResult, AssertSpec, KeyStep, Screen

DEFAULT_WAIT_TIMEOUT_MS = 5000
DEFAULT_POLL_INTERVAL_MS = 50


class ScreenTimeoutError(RuntimeError):
    pass


class ScreenAdapter(ABC):
    @abstractmethod
    def read_screen(self) -> Screen:
        ...

    @abstractmethod
    def send_keys(self, step: KeyStep) -> Screen:
        ...

    @abstractmethod
    def assert_state(self, spec: AssertSpec) -> AssertResult:
        ...

    def wait_for_screen(
        self,
        expected: str | None = None,
        timeout_ms: int = DEFAULT_WAIT_TIMEOUT_MS,
        poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS,
    ) -> Screen:
        deadline = time.monotonic() + timeout_ms / 1000.0
        while True:
            screen = self.read_screen()
            if screen.ready and (expected is None or screen.screen == expected):
                return screen
            if time.monotonic() >= deadline:
                raise ScreenTimeoutError(
                    f"screen not ready within {timeout_ms}ms "
                    f"(expected={expected}, last={screen.screen}, ready={screen.ready})"
                )
            time.sleep(poll_interval_ms / 1000.0)
