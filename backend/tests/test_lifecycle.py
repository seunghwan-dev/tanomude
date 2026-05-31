from pathlib import Path

import app as app_pkg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db import SessionLocal as MockSessionLocal
from app.main import app as mock_app
from app.models import MockSession, TripApplication
from adapter.base import ScreenAdapter
from adapter.mock_adapter import MockAdapter
from backend.coreloop import run_task
from backend.slotfill import RequestInput, SlotParseError, Slots

MOCK_ROOT = Path(app_pkg.__file__).resolve().parent.parent
SLOTS = Slots(dest_code="OSAKA", purpose="製品X納入調整")


class _Boom(RuntimeError):
    pass


class _LifecycleSpy(ScreenAdapter):
    def __init__(self, inner: ScreenAdapter, fail_on_send: bool = False):
        self._inner = inner
        self._fail_on_send = fail_on_send
        self.opened = 0
        self.closed = 0

    def open(self, idempotency_key=None):
        self.opened += 1
        return self._inner.open(idempotency_key)

    def close(self) -> None:
        self.closed += 1
        self._inner.close()

    def read_screen(self):
        return self._inner.read_screen()

    def send_keys(self, step):
        if self._fail_on_send:
            raise _Boom("injected adapter failure")
        return self._inner.send_keys(step)

    def assert_state(self, spec):
        return self._inner.assert_state(spec)


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
    return RequestInput(workflow="shukko", instruction="出張申請", fields=fields)


def _constant(slots: Slots):
    return lambda request, context: slots


def test_close_called_on_submitted_path(mock_client):
    spy = _LifecycleSpy(MockAdapter(mock_client))
    outcome = run_task(_request(), spy, _constant(SLOTS))
    assert outcome.status == "submitted"
    assert spy.opened == 1
    assert spy.closed == 1


def test_refusal_path_never_opens_adapter(mock_client):
    spy = _LifecycleSpy(MockAdapter(mock_client))
    outcome = run_task(_request(dest=""), spy, _constant(SLOTS))
    assert outcome.status == "refused"
    assert spy.opened == 0
    assert spy.closed == 0


def test_parse_failed_path_never_opens_adapter(mock_client):
    def failing(request, context):
        raise SlotParseError(retry_count=2, errors=["unparseable"])

    spy = _LifecycleSpy(MockAdapter(mock_client))
    outcome = run_task(_request(), spy, failing)
    assert outcome.status == "parse_failed"
    assert spy.opened == 0
    assert spy.closed == 0


def test_close_called_on_error_path(mock_client):
    spy = _LifecycleSpy(MockAdapter(mock_client), fail_on_send=True)
    with pytest.raises(_Boom):
        run_task(_request(), spy, _constant(SLOTS))
    assert spy.opened == 1
    assert spy.closed == 1
