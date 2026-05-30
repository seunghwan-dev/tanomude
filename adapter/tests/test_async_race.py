import inspect

import pytest

from adapter import base, mock_adapter
from adapter.mock_adapter import MockAdapter
from adapter.types import KeyStep, Screen, evaluate_assert

HAPPY = [
    KeyStep(type="nav", key="Enter"),
    KeyStep(type="field", target="DEST", value="OSAKA"),
    KeyStep(type="field", target="DEPTDATE", value="20260610"),
    KeyStep(type="field", target="RETDATE", value="20260611"),
    KeyStep(type="field", target="DAYS", value="2"),
    KeyStep(type="field", target="PURPOSE", value="製品X納入調整"),
    KeyStep(type="fkey", key="F4"),
    KeyStep(type="field", target="PROJ", value="P-001"),
    KeyStep(type="fkey", key="Enter"),
    KeyStep(type="fkey", key="Enter"),
]


def _drive(client) -> Screen:
    adapter = MockAdapter(client)
    adapter.open()
    adapter.send_keys(KeyStep(type="nav", key="Enter"))
    adapter.wait_for_screen()
    for step in HAPPY:
        adapter.send_keys(step)
        adapter.wait_for_screen()
    return adapter.read_screen()


def test_async_race_login_apply(mock_client, monkeypatch):
    monkeypatch.setenv("MOCK_AS400_RENDER_DELAY_MS", "800")
    monkeypatch.setenv("MOCK_AS400_RENDER_JITTER_MS", "1200")
    screen = _drive(mock_client)
    assert screen.screen == "submitted"
    assert screen.ready is True
    assert screen.trip_id is not None


def test_async_race_zero_delay_control(mock_client):
    screen = _drive(mock_client)
    assert screen.screen == "submitted"
    assert screen.trip_id is not None


class _StuckAdapter(base.ScreenAdapter):
    def read_screen(self) -> Screen:
        return Screen(screen="login", ready=False)

    def send_keys(self, step) -> Screen:
        return self.read_screen()

    def assert_state(self, spec):
        return evaluate_assert(self.read_screen(), spec)


def test_wait_for_screen_raises_on_timeout_without_silent_pass():
    with pytest.raises(base.ScreenTimeoutError):
        _StuckAdapter().wait_for_screen(timeout_ms=100, poll_interval_ms=10)


def test_no_blind_sleep_in_adapter_sync_path():
    assert "sleep" not in inspect.getsource(mock_adapter)
    base_source = inspect.getsource(base)
    assert base_source.count("time.sleep") == 1
    assert "wait_for_timeout" not in base_source
