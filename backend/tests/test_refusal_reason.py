from backend.slotfill import (
    EXTRACTION_MISSING_REASON,
    MALFORMED_DATE_REASON,
    REQUIRED_FIELDS_REASON,
    RequestInput,
    Slots,
    fill,
)


def _request(**overrides) -> RequestInput:
    fields = {"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11", "proj_hint": "P-001"}
    fields.update(overrides)
    return RequestInput(workflow="shutchou", instruction="出張申請", fields=fields)


def _ok_slots(request, context) -> Slots:
    return Slots(dest_code="OSAKA", purpose="製品X納入調整")


def test_required_fields_missing_reason_is_japanese():
    result = fill(_request(dest=""), _ok_slots)
    assert result.kind == "refusal"
    assert result.missing_fields == ["DEST"]
    assert result.reason == REQUIRED_FIELDS_REASON
    assert result.reason == "必須項目が入力されていません。不足している項目をご入力のうえ、再度お試しください。"


def test_malformed_date_reason_is_japanese():
    result = fill(_request(dept_date="2026-13-99"), _ok_slots)
    assert result.kind == "refusal"
    assert result.missing_fields == ["DEPTDATE"]
    assert result.reason == MALFORMED_DATE_REASON
    assert result.reason == "日付の形式が正しくありません。出発日・帰着日をご確認のうえ、修正して再入力してください。"


def test_extraction_missing_reason_is_japanese():
    result = fill(_request(), lambda request, context: Slots(dest_code="", purpose="製品X納入調整"))
    assert result.kind == "refusal"
    assert result.missing_fields == ["DEST"]
    assert result.reason == EXTRACTION_MISSING_REASON
    assert result.reason == "必須項目の値を取得できませんでした。入力内容をご確認のうえ、修正して再度お試しください。"
