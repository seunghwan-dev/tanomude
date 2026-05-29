from backend.slotfill import (
    RESULT_ADAPTER,
    FilledKeysequence,
    RequestInput,
    Refusal,
    Slots,
    fill,
    required_missing,
)


def _slots(**overrides) -> Slots:
    base = dict(dest_code="OSAKA", purpose="製品X納入調整", overseas=False, reuse_prev_proj=False)
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


def _value(result, target):
    return next(s.value for s in result.steps if s.target == target)


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
    assert result.missing_fields == ["DEST"]
    assert called == []


def test_fill_normal_assembles_keysequence():
    result = fill(_request(), _constant(_slots()))
    assert isinstance(result, FilledKeysequence)
    tokens = _tokens(result.steps)
    assert tokens[0] == ("nav", None, None, "Enter")
    assert ("field", "DEST", "OSAKA", None) in tokens
    assert ("field", "PROJ", "P-001", None) in tokens
    assert tokens[-1] == ("fkey", None, None, "Enter")


def test_dates_parsed_from_fields_iso_format():
    result = fill(_request(dept_date="2026-07-01", ret_date="2026-07-04"), _constant(_slots()))
    assert _value(result, "DEPTDATE") == "20260701"
    assert _value(result, "RETDATE") == "20260704"
    assert _value(result, "DAYS") == "4"


def test_dates_parsed_from_fields_yyyymmdd_format():
    result = fill(_request(dept_date="20260701", ret_date="20260704"), _constant(_slots()))
    assert _value(result, "DEPTDATE") == "20260701"
    assert _value(result, "DAYS") == "4"


def test_malformed_date_refuses_without_crash():
    result = fill(_request(dept_date="2026/13/40"), _constant(_slots()))
    assert isinstance(result, Refusal)
    assert "DEPTDATE" in result.missing_fields


def test_proj_read_from_fields_prefers_resolved():
    result = fill(_request(proj_hint="PX-001", proj_resolved="P-002"), _constant(_slots()))
    assert _value(result, "PROJ") == "P-002"


def test_days_recalculated_ignores_llm():
    result = fill(_request(dept_date="2026-07-01", ret_date="2026-07-04"), _constant(_slots()))
    assert _value(result, "DAYS") == "4"


def test_purpose_truncated_to_20():
    long_purpose = "実験機B定期点検および部品交換と供給状況確認次期計画打合せ"
    result = fill(_request(), _constant(_slots(purpose=long_purpose)))
    assert len(_value(result, "PURPOSE")) == 20
    assert _value(result, "PURPOSE") == long_purpose[:20]


def test_overseas_branch_inserts_ovrsea():
    result = fill(_request(proj_hint="P-003"), _constant(_slots(overseas=True)))
    tokens = _tokens(result.steps)
    assert ("fkey", None, None, "Tab") in tokens
    assert ("field", "OVRSEA", "Y", None) in tokens


def test_reuse_branch_uses_f9_not_f4():
    result = fill(_request(proj_reuse=True), _constant(_slots(reuse_prev_proj=True)))
    fkeys = [s.key for s in result.steps if s.type == "fkey"]
    assert "FieldExit" in fkeys
    assert "F9" in fkeys
    assert "F4" not in fkeys


def test_discriminated_union_roundtrips_from_json():
    refusal = fill(_request(dest=""), _constant(_slots()))
    filled = fill(_request(), _constant(_slots()))
    reparsed_refusal = RESULT_ADAPTER.validate_json(refusal.model_dump_json())
    reparsed_filled = RESULT_ADAPTER.validate_json(filled.model_dump_json())
    assert isinstance(reparsed_refusal, Refusal)
    assert isinstance(reparsed_filled, FilledKeysequence)
