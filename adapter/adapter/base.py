from abc import ABC, abstractmethod

from adapter.types import AssertResult, AssertSpec, KeyStep, Screen


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
