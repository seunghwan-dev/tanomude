import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from backend.corrections import (
    create_correction,
    deactivate_correction,
    match_corrections,
)
from backend.db import SessionLocal
from backend.models import PersonalCorrection


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


def _fields() -> dict:
    return {"dest": "大阪", "dept_date": "2026-06-10", "ret_date": "2026-06-11"}


def _active_count(platform_db, workflow: str, trigger: dict) -> int:
    return platform_db.scalar(
        select(func.count())
        .select_from(PersonalCorrection)
        .where(
            PersonalCorrection.workflow == workflow,
            PersonalCorrection.status == "active",
            PersonalCorrection.trigger == trigger,
        )
    )


def test_create_first_is_version_one(platform_db):
    correction = create_correction(
        platform_db, "shukko", {"dest": "大阪"}, "案件コード補完", "seed"
    )
    assert correction.version == 1
    assert correction.supersedes_id is None
    assert correction.status == "active"


def test_create_same_lineage_supersedes_and_keeps_single_active(platform_db):
    trigger = {"dest": "大阪"}
    first = create_correction(platform_db, "shukko", trigger, "旧ルール", "seed")
    second = create_correction(platform_db, "shukko", trigger, "新ルール", "human_revise")

    platform_db.expire_all()
    assert platform_db.get(PersonalCorrection, first.id).status == "superseded"
    assert second.version == 2
    assert second.supersedes_id == first.id
    assert second.status == "active"
    assert _active_count(platform_db, "shukko", trigger) == 1


def test_create_three_times_chain_is_intact(platform_db):
    trigger = {"dest": "大阪"}
    v1 = create_correction(platform_db, "shukko", trigger, "v1", "seed")
    v2 = create_correction(platform_db, "shukko", trigger, "v2", "human_revise")
    v3 = create_correction(platform_db, "shukko", trigger, "v3", "human_revise")

    platform_db.expire_all()
    assert _active_count(platform_db, "shukko", trigger) == 1
    assert platform_db.get(PersonalCorrection, v3.id).status == "active"
    assert platform_db.get(PersonalCorrection, v1.id).status == "superseded"
    assert platform_db.get(PersonalCorrection, v2.id).status == "superseded"
    assert v3.version == 3
    assert v3.supersedes_id == v2.id
    assert v2.supersedes_id == v1.id
    assert v1.supersedes_id is None


def test_create_different_trigger_is_separate_lineage(platform_db):
    create_correction(platform_db, "shukko", {"dest": "大阪"}, "大阪ルール", "seed")
    other = create_correction(platform_db, "shukko", {"dest": "神戸"}, "神戸ルール", "seed")
    assert other.version == 1
    assert other.supersedes_id is None
    assert _active_count(platform_db, "shukko", {"dest": "大阪"}) == 1
    assert _active_count(platform_db, "shukko", {"dest": "神戸"}) == 1


def test_index_blocks_two_active_in_same_lineage(platform_db):
    trigger = {"dest": "大阪"}
    platform_db.add(
        PersonalCorrection(
            workflow="shukko", trigger=trigger, correction_text="一号", version=1, source="seed", status="active"
        )
    )
    platform_db.commit()
    platform_db.add(
        PersonalCorrection(
            workflow="shukko", trigger=trigger, correction_text="二号", version=1, source="seed", status="active"
        )
    )
    with pytest.raises(IntegrityError):
        platform_db.commit()


def test_deactivate_retires_and_drops_from_match(platform_db):
    correction = create_correction(
        platform_db, "shukko", {"dest": "大阪"}, "案件コード補完", "seed"
    )
    assert [row.id for row in match_corrections(platform_db, "shukko", _fields())] == [correction.id]

    deactivate_correction(platform_db, correction.id)

    platform_db.expire_all()
    assert platform_db.get(PersonalCorrection, correction.id).status == "retired"
    assert match_corrections(platform_db, "shukko", _fields()) == []
