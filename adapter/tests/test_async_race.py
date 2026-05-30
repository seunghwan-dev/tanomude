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

GUARANTEED_DELAY_MS = "800"
RENDER_JITTER_MS = "1200"


def _inject_guaranteed_delay(monkeypatch):
    monkeypatch.setenv("MOCK_AS400_RENDER_DELAY_MS", GUARANTEED_DELAY_MS)
    monkeypatch.setenv("MOCK_AS400_RENDER_JITTER_MS", RENDER_JITTER_MS)


def _drive_waiting(client) -> tuple[Screen, bool]:
    adapter = MockAdapter(client)
    adapter.open()
    busy_observed = False
    held = adapter.send_keys(KeyStep(type="nav", key="Enter"))
    busy_observed = busy_observed or held.ready is False
    adapter.wait_for_screen()
    for step in HAPPY:
        held = adapter.send_keys(step)
        busy_observed = busy_observed or held.ready is False
        adapter.wait_for_screen()
    return adapter.read_screen(), busy_observed


def _drive_blind(client) -> Screen:
    adapter = MockAdapter(client)
    adapter.open()
    adapter.send_keys(KeyStep(type="nav", key="Enter"))
    for step in HAPPY:
        adapter.send_keys(step)
    return adapter.read_screen()


def test_async_race_login_apply(mock_client, monkeypatch):
    _inject_guaranteed_delay(monkeypatch)
    screen, busy_observed = _drive_waiting(mock_client)
    assert busy_observed is True
    assert screen.screen == "submitted"
    assert screen.ready is True
    assert screen.trip_id is not None


def test_async_race_zero_delay_control(mock_client):
    screen, busy_observed = _drive_waiting(mock_client)
    assert busy_observed is False
    assert screen.screen == "submitted"
    assert screen.trip_id is not None


def test_blind_drive_under_delay_never_reaches_submitted(mock_client, monkeypatch):
    _inject_guaranteed_delay(monkeypatch)
    screen = _drive_blind(mock_client)
    assert screen.screen != "submitted"
    assert screen.trip_id is None


class _StuckAdapter(base.ScreenAdapter):
    def read_screen(self) -> Screen:
        return Screen(screen="login", ready=False)

    def send_keys(self, step) -> Screen:
        return self.read_screen()

    def assert_state(self, spec):
        return evaluate_assert(self.read_screen(), spec)

    def open(self, idempotency_key=None):
        return None

    def close(self) -> None:
        return None


def test_wait_for_screen_raises_on_timeout_without_silent_pass():
    with pytest.raises(base.ScreenTimeoutError):
        _StuckAdapter().wait_for_screen(timeout_ms=100, poll_interval_ms=10)


def test_only_sleep_in_sync_path_is_the_wait_for_screen_poll():
    assert "sleep" not in inspect.getsource(mock_adapter)
    poll_source = inspect.getsource(base.ScreenAdapter.wait_for_screen)
    assert "time.sleep" in poll_source
    base_outside_poll = inspect.getsource(base).replace(poll_source, "")
    assert "time.sleep" not in base_outside_poll
    assert "wait_for_timeout" not in inspect.getsource(base)
