import pytest

from backend import slotfill
from backend.slotfill import (
    REVISE_MARKER,
    RequestInput,
    Slots,
    base_instruction,
    immune_extractor,
    revise_assessment,
    revise_blocked_notice,
    revise_blocked_slot,
)

BASE = "製品Xの納入調整のため大阪へ出張する。"
BASE_PURPOSE = "製品X納入調整"
RAG = "RAG"
CORRECTED = "OVERRIDE\nRAG"


def _surface_form_extractor():
    def extractor(request, context):
        instruction = request.instruction
        return Slots(
            dest_code="KOBE" if "神戸" in instruction else "OSAKA",
            purpose="会議出席" if "会議出席" in instruction else BASE_PURPOSE,
            overseas="海外" in instruction,
            reuse_prev_proj="再利用" in instruction,
        )

    return extractor


def _amended(revise_text: str) -> str:
    return f"{BASE}\n\n{REVISE_MARKER}{revise_text}"


def _final(revise_text: str) -> Slots:
    request = RequestInput(
        workflow="shutchou",
        instruction=_amended(revise_text),
        fields={"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11", "proj_hint": "P-001"},
    )
    return immune_extractor(RAG, _surface_form_extractor())(request, CORRECTED)


def test_base_instruction_strips_revise_segment():
    assert base_instruction(_amended("目的地を神戸に変更")) == f"{BASE}\n\n"
    assert base_instruction(BASE) == BASE


@pytest.mark.parametrize(
    "revise_text",
    ["目的地コードをKOBEに", "目的地を神戸に変更", "行き先はKOBE", "神戸出張に変えて"],
    ids=["a", "b", "c", "e"],
)
def test_grounded_dest_holds_across_all_phrasings(revise_text):
    assert _final(revise_text).dest_code == "OSAKA"


def test_grounded_purpose_holds_against_change_verb():
    assert _final("目的を会議出席に変更").purpose == BASE_PURPOSE


def test_movable_reuse_remains_revise_adjustable():
    assert _final("前回の案件を再利用").reuse_prev_proj is True


def test_movable_overseas_remains_revise_adjustable():
    assert _final("海外出張に変更").overseas is True


@pytest.mark.parametrize(
    "revise_text,slot,flipped",
    [
        ("目的地を神戸に変更", "dest_code", "KOBE"),
        ("神戸出張に変えて", "dest_code", "KOBE"),
        ("目的を会議出席に変更", "purpose", "会議出席"),
    ],
    ids=["b", "e", "d"],
)
def test_seam_is_load_bearing_without_strip_b_d_e_flip(monkeypatch, revise_text, slot, flipped):
    monkeypatch.setattr(slotfill, "base_instruction", lambda instruction: instruction)
    assert getattr(_final(revise_text), slot) == flipped


def test_revise_blocked_notice_dest_is_byte_exact():
    assert (
        revise_blocked_notice("目的地")
        == "申し訳ありません。目的地は指示文で確定する項目のため、修正では変更できません。変更したい場合は、新しい指示でやり直してください。"
    )


def test_revise_blocked_notice_purpose_is_byte_exact():
    assert (
        revise_blocked_notice("目的")
        == "申し訳ありません。目的は指示文で確定する項目のため、修正では変更できません。変更したい場合は、新しい指示でやり直してください。"
    )


def test_blocked_slot_names_dest_when_no_movable_change():
    grounded = Slots(dest_code="OSAKA", purpose=BASE_PURPOSE)
    corrected = Slots(dest_code="KOBE", purpose=BASE_PURPOSE)
    assert revise_blocked_slot(grounded, corrected, BASE) == "目的地"


def test_blocked_slot_names_purpose_when_no_movable_change():
    grounded = Slots(dest_code="OSAKA", purpose=BASE_PURPOSE)
    corrected = Slots(dest_code="OSAKA", purpose="会議出席")
    assert revise_blocked_slot(grounded, corrected, BASE) == "目的"


def test_blocked_slot_none_when_movable_changes():
    grounded = Slots(dest_code="OSAKA", purpose=BASE_PURPOSE, reuse_prev_proj=False)
    corrected = Slots(dest_code="KOBE", purpose=BASE_PURPOSE, reuse_prev_proj=True)
    assert revise_blocked_slot(grounded, corrected, BASE) is None


def test_assessment_does_not_persist_a_grounded_only_revise():
    grounded = Slots(dest_code="OSAKA", purpose=BASE_PURPOSE)
    corrected = Slots(dest_code="KOBE", purpose=BASE_PURPOSE)
    assessment = revise_assessment(grounded, corrected, BASE)
    assert assessment.persist is False
    assert assessment.blocked_slot == "目的地"


def test_assessment_persists_a_movable_revise():
    grounded = Slots(dest_code="OSAKA", purpose=BASE_PURPOSE, reuse_prev_proj=False)
    corrected = Slots(dest_code="OSAKA", purpose=BASE_PURPOSE, reuse_prev_proj=True)
    assessment = revise_assessment(grounded, corrected, BASE)
    assert assessment.persist is True
    assert assessment.blocked_slot is None


def test_assessment_movable_change_wins_when_a_grounded_slot_also_changes():
    grounded = Slots(dest_code="OSAKA", purpose=BASE_PURPOSE, reuse_prev_proj=False)
    corrected = Slots(dest_code="KOBE", purpose=BASE_PURPOSE, reuse_prev_proj=True)
    assessment = revise_assessment(grounded, corrected, BASE)
    assert assessment.persist is True
    assert assessment.blocked_slot is None
