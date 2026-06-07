import pytest

from adapter.base import ScreenAdapter
from adapter.types import AssertResult, KeyStep, Screen
from backend.coreloop import run_task
from backend.slotfill import OUT_OF_DOMAIN_REASON, RequestInput, Slots

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


def _request(instruction: str = "出張申請", **overrides) -> RequestInput:
    fields = {"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11", "proj_hint": "P-001"}
    fields.update(overrides)
    return RequestInput(workflow="shukko", instruction=instruction, fields=fields)


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


OUT_OF_DOMAIN_INSTRUCTIONS = [
    "経費精算の承認をお願いします。請求書を発行してください。",
    "在庫を確認してください。",
    "給与明細を発行してください。",
    "システムにログインしてレポートを出力してください。",
]

IN_DOMAIN_INSTRUCTIONS = [
    "出張申請",
    "製品Xの納入調整のため大阪へ出張する。",
    "大阪へ出張する。",
    "京都へ国内出張する。",
]


@pytest.mark.parametrize("instruction", OUT_OF_DOMAIN_INSTRUCTIONS)
def test_out_of_domain_instruction_refuses_without_llm_or_execution(instruction):
    calls: list[RequestInput] = []

    def slot_fn(request, context):
        calls.append(request)
        return SLOTS

    adapter = _SpyAdapter()
    outcome = run_task(_request(instruction=instruction), adapter, slot_fn)

    assert outcome.status == "refused"
    assert outcome.refusal is not None
    assert outcome.refusal.reason == OUT_OF_DOMAIN_REASON
    assert outcome.refusal.missing_fields == []
    assert calls == []
    assert adapter.opened == 0
    assert adapter.sent == []


@pytest.mark.parametrize("instruction", IN_DOMAIN_INSTRUCTIONS)
def test_in_domain_instruction_passes_gate_to_extraction(instruction):
    calls: list[RequestInput] = []

    def slot_fn(request, context):
        calls.append(request)
        return SLOTS

    adapter = _SpyAdapter()
    outcome = run_task(_request(instruction=instruction), adapter, slot_fn)

    assert len(calls) == 1
    assert not (outcome.refusal is not None and outcome.refusal.reason == OUT_OF_DOMAIN_REASON)
