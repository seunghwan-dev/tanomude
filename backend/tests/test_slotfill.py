from backend.slotfill import (
    FilledKeysequence,
    RequestInput,
    Refusal,
    Slots,
    fill,
    required_missing,
)


def _slots(**overrides) -> Slots:
    base = dict(
        dest_code="OSAKA",
        dept_date="20260610",
        ret_date="20260611",
        purpose="製品X納入調整",
        proj_code="P-001",
        overseas=False,
        reuse_prev_proj=False,
    )
    base.update(overrides)
    return Slots(**base)


def _constant(slots: Slots):
    return lambda request, context: slots


def _request(**field_overrides) -> RequestInput:
    fields = {"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11", "proj_hint": "P-001"}
    fields.update(field_overrides)
    return RequestInput(workflow="shukko", instruction="出張申請", fields=fields)


def _tokens(steps):
    return [(s.type, s.target, s.value, s.key) for s in steps]


def test_required_missing_flags_empty_dest():
    assert required_missing({"dest": "", "dept_date": "20260620", "ret_date": "20260620", "proj_hint": "P-001"}) == ["DEST"]


def test_required_missing_accepts_proj_reuse():
    assert required_missing({"dest": "TOKYO", "dept_date": "20260601", "ret_date": "20260601", "proj_reuse": True}) == []


def test_fill_refuses_without_invoking_llm():
    called = []

    def slot_fn(request, context):
        called.append(1)
        return _slots()

    result = fill(_request(dest=""), slot_fn)
    assert isinstance(result, Refusal)
    assert result.kind == "refusal"
    assert result.missing_fields == ["DEST"]
    assert called == []


def test_fill_normal_assembles_keysequence():
    result = fill(_request(), _constant(_slots()))
    assert isinstance(result, FilledKeysequence)
    assert result.kind == "filled"
    tokens = _tokens(result.steps)
    assert tokens[0] == ("nav", None, None, "Enter")
    assert ("field", "DEST", "OSAKA", None) in tokens
    assert ("fkey", None, None, "F4") in tokens
    assert tokens[-1] == ("fkey", None, None, "Enter")


def test_purpose_truncated_to_20():
    long_purpose = "実験機B定期点検および部品交換と供給状況確認次期計画打合せ"
    result = fill(_request(), _constant(_slots(purpose=long_purpose)))
    purpose_step = next(s for s in result.steps if s.target == "PURPOSE")
    assert len(purpose_step.value) == 20
    assert purpose_step.value == long_purpose[:20]


def test_days_recalculated_from_dates():
    result = fill(_request(), _constant(_slots(dept_date="20260701", ret_date="20260704")))
    days_step = next(s for s in result.steps if s.target == "DAYS")
    assert days_step.value == "4"


def test_overseas_branch_inserts_ovrsea():
    result = fill(_request(), _constant(_slots(overseas=True, proj_code="P-003")))
    tokens = _tokens(result.steps)
    assert ("fkey", None, None, "Tab") in tokens
    assert ("field", "OVRSEA", "Y", None) in tokens


def test_reuse_branch_uses_f9_not_f4():
    result = fill(_request(), _constant(_slots(reuse_prev_proj=True, proj_code="P-002")))
    fkeys = [s.key for s in result.steps if s.type == "fkey"]
    assert "FieldExit" in fkeys
    assert "F9" in fkeys
    assert "F4" not in fkeys


def test_result_union_discriminators():
    filled = fill(_request(), _constant(_slots()))
    refusal = fill(_request(dest=""), _constant(_slots()))
    assert filled.kind == "filled"
    assert refusal.kind == "refusal"
