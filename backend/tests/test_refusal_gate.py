import pytest

from adapter.base import ScreenAdapter
from adapter.types import AssertResult, KeyStep, Screen
from backend.coreloop import run_task
from backend.slotfill import RequestInput, Slots

SLOTS = Slots(dest_code="OSAKA", purpose="製品X納入調整")


class _SpyAdapter(ScreenAdapter):
    def __init__(self):
        self.opened = 0
        self.sent: list[KeyStep] = []

    def open(self, idempotency_key: str | None = None) -> Screen | None:
        self.opened += 1
        return None

    def close(self) -> None:
        pass

    def read_screen(self) -> Screen:
        return Screen(screen="login")

    def send_keys(self, step: KeyStep) -> Screen:
        self.sent.append(step)
        return Screen(screen="login")

    def assert_state(self, spec) -> AssertResult:
        return AssertResult(ok=False)


def _request(**overrides) -> RequestInput:
    fields = {"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11", "proj_hint": "P-001"}
    fields.update(overrides)
    return RequestInput(workflow="shukko", instruction="出張申請", fields=fields)


@pytest.mark.parametrize(
    "field,missing",
    [("dest", "DEST"), ("dept_date", "DEPTDATE"), ("ret_date", "RETDATE"), ("proj_hint", "PROJ")],
)
def test_empty_required_field_refuses_without_llm_or_execution(field, missing):
    calls: list[RequestInput] = []

    def slot_fn(request, context):
        calls.append(request)
        return SLOTS

    adapter = _SpyAdapter()
    outcome = run_task(_request(**{field: ""}), adapter, slot_fn)

    assert outcome.status == "refused"
    assert outcome.refusal is not None
    assert missing in outcome.refusal.missing_fields
    assert calls == []
    assert adapter.opened == 0
    assert adapter.sent == []


def test_malformed_date_refuses_without_llm_or_execution():
    calls: list[RequestInput] = []

    def slot_fn(request, context):
        calls.append(request)
        return SLOTS

    adapter = _SpyAdapter()
    outcome = run_task(_request(dept_date="2026-13-99"), adapter, slot_fn)

    assert outcome.status == "refused"
    assert outcome.refusal is not None
    assert "DEPTDATE" in outcome.refusal.missing_fields
    assert calls == []
    assert adapter.opened == 0
