import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

from backend.corrections import apply_corrections, create_correction, match_corrections
from backend.db import SessionLocal
from backend.models import OperationDoc, PersonalCorrection, Task

MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "0011_rename_workflow_identifier.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("rename_migration_0011", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration = _load_migration()
OLD = migration.OLD_WORKFLOW
NEW = migration.NEW_WORKFLOW


@pytest.fixture
def platform_db():
    session = SessionLocal()
    _purge(session)
    try:
        yield session
    finally:
        session.rollback()
        _purge(session)
        session.close()


def _purge(session) -> None:
    for model in (PersonalCorrection, Task, OperationDoc):
        session.execute(delete(model).where(model.workflow.in_((OLD, NEW))))
    session.commit()


def _fields() -> dict:
    return {"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11"}


def test_existing_correction_reapplies_under_new_identifier(platform_db):
    correction = create_correction(
        platform_db, OLD, {"dest": "大阪"}, "大阪は前回案件コードを再利用する", "seed"
    )
    assert match_corrections(platform_db, NEW, _fields()) == []

    migration.rewrite_workflow(platform_db, OLD, NEW)
    platform_db.commit()

    matched = match_corrections(platform_db, NEW, _fields())
    assert [row.id for row in matched] == [correction.id]
    assert match_corrections(platform_db, OLD, _fields()) == []

    context, fallback = apply_corrections(platform_db, NEW, _fields(), "RAG-BASE")
    assert correction.correction_text in context
    assert fallback == []


def test_rewrite_clears_all_workflow_columns_and_preserves_source(platform_db):
    platform_db.add(Task(dedup_key=None, workflow=OLD, instruction="出張申請", fields={}, status="refused"))
    create_correction(platform_db, OLD, {"dest": "大阪"}, "テスト補正", "seed")
    doc_source = "shukko_manual.md"
    platform_db.add(OperationDoc(workflow=OLD, title="出張申請 操作マニュアル", source=doc_source))
    platform_db.commit()

    migration.rewrite_workflow(platform_db, OLD, NEW)
    platform_db.commit()

    for model in (Task, PersonalCorrection, OperationDoc):
        remaining = platform_db.scalar(
            select(func.count()).select_from(model).where(model.workflow == OLD)
        )
        assert remaining == 0

    doc = platform_db.scalar(
        select(OperationDoc).where(OperationDoc.workflow == NEW, OperationDoc.source == doc_source)
    )
    assert doc is not None
