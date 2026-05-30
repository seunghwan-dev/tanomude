import httpx

from adapter.base import ScreenAdapter
from adapter.types import AssertResult, AssertSpec, KeyStep, Screen, evaluate_assert


class MockAdapter(ScreenAdapter):
    def __init__(self, client: httpx.Client):
        self._client = client
        self._session_id: str | None = None

    def open(self, idempotency_key: str | None = None) -> Screen:
        response = self._client.post("/session", json={"idempotency_key": idempotency_key})
        response.raise_for_status()
        screen = Screen.model_validate(response.json())
        self._session_id = screen.session_id
        return screen

    def read_screen(self) -> Screen:
        self._require_session()
        response = self._client.get(f"/session/{self._session_id}")
        response.raise_for_status()
        return Screen.model_validate(response.json())

    def send_keys(self, step: KeyStep) -> Screen:
        self._require_session()
        response = self._client.post(f"/session/{self._session_id}/step", json=step.model_dump())
        response.raise_for_status()
        return Screen.model_validate(response.json())

    def assert_state(self, spec: AssertSpec) -> AssertResult:
        return evaluate_assert(self.read_screen(), spec)

    def _require_session(self) -> None:
        if self._session_id is None:
            raise RuntimeError("adapter session not opened")
