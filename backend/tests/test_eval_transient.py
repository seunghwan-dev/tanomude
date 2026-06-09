from pathlib import Path

import app as app_pkg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete

from adapter.base import ScreenAdapter
from adapter.mock_adapter import MockAdapter
from adapter.types import AssertResult, KeyStep, Screen
from app.db import SessionLocal as MockSessionLocal
from app.main import app as mock_app
from app.models import MockSession, TripApplication
from backend.coreloop import MAX_REPLAN, run_task
from backend.eval_dataset import EVAL_CASES
from backend.eval_transient import CONFIRM_SCREEN, TransientAdapter, fail_submits_for
from backend.slotfill import RequestInput, Slots

MOCK_ROOT = Path(app_pkg.__file__).resolve().parent.parent
SLOTS = Slots(dest_code="OSAKA", purpose="製品X納入調整")
ENTER = KeyStep(type="nav", key="Enter")


class _FakeAdapter(ScreenAdapter):
    def __init__(self, screen: str):
        self._screen = screen
        self.sent: list[KeyStep] = []

    def open(self, idempotency_key: str | None = None) -> Screen | None:
        return None

    def close(self) -> None:
        pass

    def read_screen(self) -> Screen:
        return Screen(screen=self._screen)

    def send_keys(self, step: KeyStep) -> Screen:
        self.sent.append(step)
        return Screen(screen="submitted")

    def assert_state(self, spec) -> AssertResult:
        return AssertResult(ok=True)


def _case(case_id: str):
    return next(case for case in EVAL_CASES if case.case_id == case_id)


def test_wrapper_swallows_confirm_submit_k_times():
    fake = _FakeAdapter(CONFIRM_SCREEN)
    wrapper = TransientAdapter(fake, fail_submits=2)
    assert wrapper.send_keys(ENTER).screen == CONFIRM_SCREEN
    assert wrapper.send_keys(ENTER).screen == CONFIRM_SCREEN
    assert fake.sent == []
    assert wrapper.send_keys(ENTER).screen == "submitted"
    assert len(fake.sent) == 1
    assert wrapper.swallowed == 2


def test_wrapper_zero_fail_submits_delegates_immediately():
    fake = _FakeAdapter(CONFIRM_SCREEN)
    wrapper = TransientAdapter(fake, fail_submits=0)
    wrapper.send_keys(ENTER)
    assert len(fake.sent) == 1
    assert wrapper.swallowed == 0


def test_wrapper_only_swallows_on_confirm_screen():
    fake = _FakeAdapter("trip_input")
    wrapper = TransientAdapter(fake, fail_submits=2)
    wrapper.send_keys(ENTER)
    assert len(fake.sent) == 1
    assert wrapper.swallowed == 0


def test_fail_submits_calibration():
    assert fail_submits_for(_case("transient_recover_01")) == 1
    assert fail_submits_for(_case("transient_recover_02")) == 1
    assert fail_submits_for(_case("transient_exhaust_01")) == MAX_REPLAN + 1
    assert fail_submits_for(_case("transient_exhaust_02")) == MAX_REPLAN + 1
    assert fail_submits_for(_case("normal_01")) == 0
    assert fail_submits_for(_case("wrong_01_px")) == 0


def test_production_execute_runner_is_unwrapped():
    from backend.agent.service import _production_execute_runner, get_execute_runner

    assert get_execute_runner() is _production_execute_runner


@pytest.fixture(scope="module", autouse=True)
def mock_schema():
    config = Config(str(MOCK_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(MOCK_ROOT / "alembic"))
    command.upgrade(config, "head")
    yield


@pytest.fixture
def mock_client():
    client = TestClient(mock_app)
    try:
        yield client
    finally:
        with MockSessionLocal() as session:
            session.execute(delete(MockSession))
            session.execute(delete(TripApplication))
            session.commit()


def _request(**overrides) -> RequestInput:
    fields = {"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11", "proj_hint": "P-001"}
    fields.update(overrides)
    return RequestInput(workflow="shutchou", instruction="出張申請", fields=fields)


def _constant(slots: Slots):
    return lambda request, context: slots


def test_transient_recover_reaches_submitted(mock_client):
    adapter = TransientAdapter(MockAdapter(mock_client), fail_submits=1)
    outcome = run_task(_request(), adapter, _constant(SLOTS))
    assert outcome.status == "submitted"
    assert outcome.trip_id is not None
    assert adapter.swallowed == 1


def test_transient_exhaust_lands_on_needs_investigation(mock_client):
    adapter = TransientAdapter(MockAdapter(mock_client), fail_submits=MAX_REPLAN + 1)
    outcome = run_task(_request(), adapter, _constant(SLOTS))
    assert outcome.status == "rolled_back"
    assert outcome.correction_candidate is not None
    assert outcome.correction_candidate.bad_data is False
    assert outcome.correction_candidate.replan_count == MAX_REPLAN
