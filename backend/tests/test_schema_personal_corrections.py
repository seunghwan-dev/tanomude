from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, inspect, select

from backend.db import SessionLocal, engine
from backend.models import PersonalCorrection

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
        session.execute(delete(PersonalCorrection))
        session.commit()
        session.close()


def _correction(platform_db, **overrides) -> PersonalCorrection:
    defaults = {
        "workflow": "shukko",
        "trigger": {"field": "dest_code", "equals": "OSAKA"},
        "correction_text": "OSAKA行きは案件コードをPROJ-Xで補完する",
        "version": 1,
        "source": "seed",
    }
    defaults.update(overrides)
    correction = PersonalCorrection(**defaults)
    platform_db.add(correction)
    platform_db.commit()
    return correction


def test_table_exists_after_migration():
    inspector = inspect(engine)
    assert inspector.has_table("personal_corrections")


def test_workflow_status_index_present():
    inspector = inspect(engine)
    indexed = [index["column_names"] for index in inspector.get_indexes("personal_corrections")]
    assert ["workflow", "status"] in indexed


def test_persist_round_trip(platform_db):
    correction = _correction(platform_db, approver="tanaka")
    with SessionLocal() as readback:
        loaded = readback.get(PersonalCorrection, correction.id)
        assert loaded.workflow == "shukko"
        assert loaded.trigger == {"field": "dest_code", "equals": "OSAKA"}
        assert loaded.correction_text == "OSAKA行きは案件コードをPROJ-Xで補完する"
        assert loaded.status == "active"
        assert loaded.version == 1
        assert loaded.supersedes_id is None
        assert loaded.source == "seed"
        assert loaded.approver == "tanaka"
        assert loaded.created_at is not None


def test_status_server_default_active(platform_db):
    correction = PersonalCorrection(
        workflow="shukko",
        trigger={"field": "dest_code", "equals": "KOBE"},
        correction_text="KOBE行きの補完",
        version=1,
        source="seed",
    )
    platform_db.add(correction)
    platform_db.commit()
    platform_db.refresh(correction)
    assert correction.status == "active"


def test_self_fk_supersedes_chain(platform_db):
    base = _correction(platform_db)
    revised = _correction(
        platform_db, version=2, supersedes_id=base.id, source="human_revise", approver="suzuki"
    )
    with SessionLocal() as readback:
        loaded = readback.get(PersonalCorrection, revised.id)
        assert loaded.supersedes_id == base.id
        assert loaded.version == 2
        assert loaded.source == "human_revise"
        parent = readback.get(PersonalCorrection, loaded.supersedes_id)
        assert parent.id == base.id
        assert parent.supersedes_id is None


def test_status_filter_query(platform_db):
    _correction(platform_db, status="active")
    _correction(platform_db, status="superseded")
    active = platform_db.scalars(
        select(PersonalCorrection).where(
            PersonalCorrection.workflow == "shukko", PersonalCorrection.status == "active"
        )
    ).all()
    assert len(active) == 1
    assert active[0].status == "active"


def test_migration_downgrade_then_upgrade_is_clean():
    config = _alembic_config()
    command.downgrade(config, "0004")
    inspector = inspect(engine)
    assert not inspector.has_table("personal_corrections")

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert inspector.has_table("personal_corrections")
    indexed = [index["column_names"] for index in inspector.get_indexes("personal_corrections")]
    assert ["workflow", "status"] in indexed
