from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import IntegrityError

from backend.db import SessionLocal, engine
from backend.models import Approval, AuditLog, Execution, Plan, Task
from backend.retrieval import RetrievedChunk

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def _alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    return config


@pytest.fixture
def platform_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(delete(AuditLog))
        session.execute(delete(Approval))
        session.execute(delete(Plan))
        session.execute(delete(Execution))
        session.execute(delete(Task))
        session.commit()
        session.close()


def _task(platform_db, **overrides) -> Task:
    defaults = {"dedup_key": None, "workflow": "shutchou", "instruction": "出張申請", "fields": {}, "status": "awaiting_approval"}
    defaults.update(overrides)
    task = Task(**defaults)
    platform_db.add(task)
    platform_db.commit()
    return task


def _grounding() -> list[dict]:
    chunk = RetrievedChunk(
        chunk_id=3, doc_id=1, section="apply", heading="申請手順", text="F4で案件を選ぶ", score=0.42, rank=1
    )
    return [chunk.model_dump()]


def test_tables_exist_after_migration():
    inspector = inspect(engine)
    assert inspector.has_table("plans")
    assert inspector.has_table("approvals")
    assert inspector.has_table("audit_log")


def test_plan_approval_audit_persist(platform_db):
    task = _task(platform_db)
    plan = Plan(
        task_id=task.id,
        version=1,
        analysis={"dest_code": "OSAKA", "purpose": "製品X納入調整"},
        keysequence=[{"seq": 1, "type": "nav", "key": "Enter"}],
        grounding=_grounding(),
        status="proposed",
    )
    platform_db.add(plan)
    platform_db.commit()

    platform_db.add(
        Approval(task_id=task.id, plan_id=plan.id, decision="approve", approver="tanaka", decision_text=None)
    )
    platform_db.add(
        AuditLog(task_id=task.id, plan_id=plan.id, approver="tanaka", decision="approve", decision_text="ok")
    )
    platform_db.commit()

    with SessionLocal() as readback:
        loaded = readback.get(Plan, plan.id)
        assert loaded.task_id == task.id
        assert loaded.version == 1
        assert loaded.analysis == {"dest_code": "OSAKA", "purpose": "製品X納入調整"}
        assert loaded.keysequence == [{"seq": 1, "type": "nav", "key": "Enter"}]
        assert loaded.status == "proposed"
        assert loaded.created_at is not None

        approval = readback.scalars(select(Approval).where(Approval.plan_id == plan.id)).one()
        assert approval.decision == "approve"
        assert approval.approver == "tanaka"
        assert approval.decision_text is None

        audit = readback.scalars(select(AuditLog).where(AuditLog.plan_id == plan.id)).one()
        assert audit.decision == "approve"
        assert audit.decision_text == "ok"
        assert audit.ts is not None


def test_grounding_jsonb_round_trip(platform_db):
    task = _task(platform_db)
    grounding = _grounding()
    plan = Plan(
        task_id=task.id, version=1, analysis={}, keysequence=[], grounding=grounding, status="proposed"
    )
    platform_db.add(plan)
    platform_db.commit()

    with SessionLocal() as readback:
        loaded = readback.get(Plan, plan.id)
        assert loaded.grounding == grounding
        assert loaded.grounding[0]["heading"] == "申請手順"
        assert loaded.grounding[0]["score"] == 0.42


def test_status_accepts_awaiting_approval(platform_db):
    task = _task(platform_db, status="awaiting_approval")
    with SessionLocal() as readback:
        assert readback.get(Task, task.id).status == "awaiting_approval"


def test_unique_task_version_conflicts(platform_db):
    task = _task(platform_db)
    platform_db.add(Plan(task_id=task.id, version=1, analysis={}, keysequence=[], grounding=[], status="proposed"))
    platform_db.commit()
    platform_db.add(Plan(task_id=task.id, version=1, analysis={}, keysequence=[], grounding=[], status="superseded"))
    with pytest.raises(IntegrityError):
        platform_db.commit()


def test_revise_keeps_plan_history(platform_db):
    task = _task(platform_db)
    platform_db.add(Plan(task_id=task.id, version=1, analysis={}, keysequence=[], grounding=[], status="superseded"))
    platform_db.add(Plan(task_id=task.id, version=2, analysis={}, keysequence=[], grounding=[], status="proposed"))
    platform_db.commit()
    versions = platform_db.scalars(
        select(Plan.version).where(Plan.task_id == task.id).order_by(Plan.version)
    ).all()
    assert list(versions) == [1, 2]


def test_delete_task_cascades_operational_rows_but_audit_survives(platform_db):
    task = _task(platform_db)
    plan = Plan(task_id=task.id, version=1, analysis={}, keysequence=[], grounding=[], status="proposed")
    platform_db.add(plan)
    platform_db.commit()
    platform_db.add(Approval(task_id=task.id, plan_id=plan.id, decision="approve", approver="tanaka"))
    platform_db.add(
        AuditLog(task_id=task.id, plan_id=plan.id, approver="tanaka", decision="approve", decision_text="ringi")
    )
    platform_db.commit()
    task_id, plan_id = task.id, plan.id

    platform_db.execute(delete(Task).where(Task.id == task_id))
    platform_db.commit()

    for model in (Plan, Approval):
        remaining = platform_db.scalar(
            select(func.count()).select_from(model).where(model.task_id == task_id)
        )
        assert remaining == 0

    witness = platform_db.scalars(select(AuditLog).where(AuditLog.task_id == task_id)).all()
    assert len(witness) == 1
    assert witness[0].task_id == task_id
    assert witness[0].plan_id == plan_id
    assert witness[0].approver == "tanaka"
    assert witness[0].decision == "approve"
    assert witness[0].decision_text == "ringi"


def test_indexes_present():
    inspector = inspect(engine)
    assert ["task_id"] in [index["column_names"] for index in inspector.get_indexes("plans")]
    assert ["plan_id"] in [index["column_names"] for index in inspector.get_indexes("approvals")]
    assert ["plan_id"] in [index["column_names"] for index in inspector.get_indexes("audit_log")]


def test_migration_downgrade_then_upgrade_is_clean():
    config = _alembic_config()
    command.downgrade(config, "0003")
    inspector = inspect(engine)
    assert not inspector.has_table("plans")
    assert not inspector.has_table("approvals")
    assert not inspector.has_table("audit_log")

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert inspector.has_table("plans")
    assert inspector.has_table("approvals")
    assert inspector.has_table("audit_log")


def test_downgrade_safe_with_awaiting_approval_rows(platform_db):
    _task(platform_db, status="awaiting_approval")
    config = _alembic_config()
    command.downgrade(config, "0003")
    command.upgrade(config, "head")
    with SessionLocal() as readback:
        surviving = readback.scalar(
            select(func.count()).select_from(Task).where(Task.status == "awaiting_approval")
        )
    assert surviving >= 1
