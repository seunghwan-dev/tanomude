import pytest
from sqlalchemy import delete, func, select

from backend.agent import service
from backend.corrections import (
    MAX_CORRECTION_LENGTH,
    OVERRIDE_HEADER,
    RAG_HEADER,
    apply_corrections,
    match_corrections,
    quarantine_correction,
    validate_correction,
)
from backend.db import SessionLocal
from backend.models import PersonalCorrection
from backend.retrieval import RetrievedChunk
from backend.slotfill import RequestInput


@pytest.fixture
def platform_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(delete(PersonalCorrection))
        session.commit()
        session.close()


def _seed(platform_db, **overrides) -> PersonalCorrection:
    defaults = {
        "workflow": "shukko",
        "trigger": {"dest": "大阪"},
        "correction_text": "大阪行きは案件コードをPROJ-Xで補完する",
        "version": 1,
        "source": "seed",
        "status": "active",
    }
    defaults.update(overrides)
    correction = PersonalCorrection(**defaults)
    platform_db.add(correction)
    platform_db.commit()
    return correction


def _fields() -> dict:
    return {"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11"}


def test_match_returns_active_workflow_and_trigger(platform_db):
    target = _seed(platform_db)
    matched = match_corrections(platform_db, "shukko", _fields())
    assert [row.id for row in matched] == [target.id]


def test_match_excludes_other_workflow(platform_db):
    _seed(platform_db, workflow="ringi")
    matched = match_corrections(platform_db, "shukko", _fields())
    assert matched == []


def test_match_excludes_non_active(platform_db):
    _seed(platform_db, status="superseded")
    _seed(platform_db, status="quarantined")
    matched = match_corrections(platform_db, "shukko", _fields())
    assert matched == []


def test_match_trigger_subset_required(platform_db):
    _seed(platform_db, trigger={"dest": "大阪", "purpose": "納入調整"})
    matched = match_corrections(platform_db, "shukko", _fields())
    assert matched == []


def test_match_empty_trigger_is_workflow_wide(platform_db):
    target = _seed(platform_db, trigger={})
    matched = match_corrections(platform_db, "shukko", {"anything": "value"})
    assert [row.id for row in matched] == [target.id]


def test_apply_prepends_override_block(platform_db):
    _seed(platform_db)
    base = "RAG-CONTEXT"
    result, _ = apply_corrections(platform_db, "shukko", _fields(), base)
    expected = (
        f"{OVERRIDE_HEADER}\n大阪行きは案件コードをPROJ-Xで補完する\n{RAG_HEADER}\nRAG-CONTEXT"
    )
    assert result == expected


def test_apply_no_match_returns_base_unchanged(platform_db):
    _seed(platform_db, workflow="ringi")
    base = "RAG-CONTEXT"
    context, _ = apply_corrections(platform_db, "shukko", _fields(), base)
    assert context == base


def test_apply_override_is_non_vacuous(platform_db):
    _seed(platform_db)
    base = "RAG-CONTEXT"
    result, _ = apply_corrections(platform_db, "shukko", _fields(), base)
    assert OVERRIDE_HEADER in result
    assert result.index("大阪行きは案件コードをPROJ-Xで補完する") < result.index(base)
    assert result.startswith(OVERRIDE_HEADER)


def test_apply_joins_multiple_matches(platform_db):
    _seed(platform_db, correction_text="教正A")
    _seed(platform_db, trigger={}, correction_text="教正B")
    result, _ = apply_corrections(platform_db, "shukko", _fields(), "BASE")
    assert "教正A" in result
    assert "教正B" in result
    assert result.index(OVERRIDE_HEADER) < result.index("教正A")


def test_apply_is_reusable_without_runner(platform_db):
    _seed(platform_db)
    augmented, _ = apply_corrections(platform_db, "shukko", _fields(), "BASE")
    assert augmented.startswith(OVERRIDE_HEADER)
    assert augmented.endswith("BASE")


def test_apply_is_read_only(platform_db):
    _seed(platform_db)
    before = platform_db.scalar(select(func.count()).select_from(PersonalCorrection))
    apply_corrections(platform_db, "shukko", _fields(), "BASE")
    after = platform_db.scalar(select(func.count()).select_from(PersonalCorrection))
    assert before == after == 1


def _correction(text: str) -> PersonalCorrection:
    return PersonalCorrection(correction_text=text)


def test_validate_accepts_normal_correction():
    assert validate_correction(_correction("大阪行きは案件コードをPROJ-Xで補完する")) is True


def test_validate_rejects_empty_or_whitespace():
    assert validate_correction(_correction("")) is False
    assert validate_correction(_correction("   ")) is False


def test_validate_rejects_over_length():
    assert validate_correction(_correction("a" * MAX_CORRECTION_LENGTH)) is True
    assert validate_correction(_correction("a" * (MAX_CORRECTION_LENGTH + 1))) is False


def test_validate_rejects_control_characters():
    assert validate_correction(_correction("汚染\x00注入")) is False


def test_apply_excludes_contaminated_keeps_valid(platform_db):
    _seed(platform_db, trigger={"dest": "大阪"}, correction_text="有効な個人教正")
    contaminated = _seed(platform_db, trigger={}, correction_text="汚染マーカー\x07注入")
    context, fallback = apply_corrections(platform_db, "shukko", _fields(), "RAG-BASE")
    assert "有効な個人教正" in context
    assert "汚染マーカー" not in context
    assert [exc.id for exc in fallback] == [contaminated.id]
    assert fallback[0].reason == "non_printable"


def test_apply_all_contaminated_falls_back_to_base(platform_db):
    _seed(platform_db, correction_text="")
    context, fallback = apply_corrections(platform_db, "shukko", _fields(), "RAG-BASE")
    assert context == "RAG-BASE"
    assert [exc.reason for exc in fallback] == ["empty"]


def test_apply_read_only_with_contamination(platform_db):
    _seed(platform_db, trigger={"dest": "大阪"}, correction_text="有効な個人教正")
    _seed(platform_db, trigger={}, correction_text="汚染\x07")
    before = platform_db.scalar(select(func.count()).select_from(PersonalCorrection))
    apply_corrections(platform_db, "shukko", _fields(), "BASE")
    after = platform_db.scalar(select(func.count()).select_from(PersonalCorrection))
    active = platform_db.scalar(
        select(func.count())
        .select_from(PersonalCorrection)
        .where(PersonalCorrection.status == "active")
    )
    assert before == after == 2
    assert active == 2


def test_quarantine_sets_status_and_excludes_from_match(platform_db):
    target = _seed(platform_db)
    quarantine_correction(platform_db, target.id)
    refreshed = platform_db.get(PersonalCorrection, target.id)
    assert refreshed.status == "quarantined"
    assert match_corrections(platform_db, "shukko", _fields()) == []


def _chunk(text: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=1, doc_id=1, section="apply", heading="申請手順", text=text, score=0.5, rank=1
    )


def test_hitl_runner_threads_correction_into_context(platform_db, monkeypatch):
    _seed(platform_db, correction_text="個人ルールX")
    captured: dict = {}

    def fake_hybrid_search(db, query):
        return [_chunk("RAG-BASE")]

    def fake_plan(request, slot_fn, context):
        captured["context"] = context
        return service.ParseFailure(errors=["stop"])

    monkeypatch.setattr(service, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(service, "plan", fake_plan)

    request = RequestInput(
        workflow="shukko",
        instruction="出張申請",
        fields=_fields(),
    )
    service._production_plan_runner(request)

    assert "個人ルールX" in captured["context"]
    assert OVERRIDE_HEADER in captured["context"]
    assert "RAG-BASE" in captured["context"]
    assert captured["context"].index("個人ルールX") < captured["context"].index("RAG-BASE")
