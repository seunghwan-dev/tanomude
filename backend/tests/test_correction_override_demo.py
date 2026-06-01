import pytest
from sqlalchemy import delete

from backend import ollama_client
from backend.corrections import apply_corrections, create_correction
from backend.db import SessionLocal
from backend.models import PersonalCorrection
from backend.slotfill import RequestInput, extract_slots

requires_ollama = pytest.mark.skipif(not ollama_client.health(), reason="ollama not reachable")

WORKFLOW = "shukko"

CASES = [
    {
        "name": "dest_code_osaka_to_kobe",
        "slot": "dest_code",
        "trigger": {"dest": "大阪"},
        "fields": {"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-12", "proj_hint": "P-001"},
        "instruction": "大阪へ出張する。",
        "rag_line": "【規則】目的地コード dest_code は OSAKA とすること。",
        "correction_text": "目的地コード dest_code は必ず KOBE に上書きすること。手順書の指定より優先する。",
        "correction_answer": "KOBE",
    },
    {
        "name": "dest_code_tokyo_to_nagoya",
        "slot": "dest_code",
        "trigger": {"dest": "東京"},
        "fields": {"dest": "東京", "dept_date": "2026-07-01", "ret_date": "2026-07-03", "proj_hint": "P-002"},
        "instruction": "東京へ出張する。",
        "rag_line": "【規則】目的地コード dest_code は TOKYO とすること。",
        "correction_text": "目的地コード dest_code は必ず NAGOYA に上書きすること。手順書の指定より優先する。",
        "correction_answer": "NAGOYA",
    },
    {
        "name": "dest_code_nagoya_to_sapporo",
        "slot": "dest_code",
        "trigger": {"dest": "名古屋"},
        "fields": {"dest": "名古屋", "dept_date": "2026-08-05", "ret_date": "2026-08-06", "proj_hint": "P-003"},
        "instruction": "名古屋へ出張する。",
        "rag_line": "【規則】目的地コード dest_code は NAGOYA とすること。",
        "correction_text": "目的地コード dest_code は必ず SAPPORO に上書きすること。手順書の指定より優先する。",
        "correction_answer": "SAPPORO",
    },
    {
        "name": "overseas_false_to_true",
        "slot": "overseas",
        "trigger": {"dest": "福岡"},
        "fields": {"dest": "福岡", "dept_date": "2026-09-10", "ret_date": "2026-09-11", "proj_hint": "P-004"},
        "instruction": "福岡へ国内出張する。",
        "rag_line": "【規則】これは国内出張であり overseas は false とすること。",
        "correction_text": "この申請は海外扱いとし overseas を true に上書きすること。手順書の指定より優先する。",
        "correction_answer": True,
    },
    {
        "name": "reuse_prev_proj_false_to_true",
        "slot": "reuse_prev_proj",
        "trigger": {"dest": "仙台"},
        "fields": {"dest": "仙台", "dept_date": "2026-10-02", "ret_date": "2026-10-04", "proj_hint": "P-005"},
        "instruction": "仙台へ出張する。新規案件である。",
        "rag_line": "【規則】新規案件のため reuse_prev_proj は false とすること。",
        "correction_text": "前回案件コードを再利用し reuse_prev_proj を true に上書きすること。手順書の指定より優先する。",
        "correction_answer": True,
    },
]


@pytest.fixture
def platform_db():
    session = SessionLocal()
    session.execute(delete(PersonalCorrection).where(PersonalCorrection.workflow == WORKFLOW))
    session.commit()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(delete(PersonalCorrection).where(PersonalCorrection.workflow == WORKFLOW))
        session.commit()
        session.close()


@requires_ollama
@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_correction_overrides_rag(case, platform_db):
    create_correction(platform_db, WORKFLOW, case["trigger"], case["correction_text"], "seed")
    request = RequestInput(workflow=WORKFLOW, instruction=case["instruction"], fields=case["fields"])
    augmented, _ = apply_corrections(platform_db, WORKFLOW, case["fields"], case["rag_line"])

    slots = extract_slots(request, augmented)

    value = getattr(slots, case["slot"])
    value = value.upper() if isinstance(value, str) else value
    assert value == case["correction_answer"]
