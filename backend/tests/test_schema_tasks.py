from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import IntegrityError

from backend.db import SessionLocal, engine
from backend.models import Execution, Task

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
        session.execute(delete(Execution))
        session.execute(delete(Task))
        session.commit()
        session.close()


def test_tables_exist_after_migration():
    inspector = inspect(engine)
    assert inspector.has_table("tasks")
    assert inspector.has_table("executions")


def test_task_and_execution_persist(platform_db):
    task = Task(
        dedup_key="task:abc",
        workflow="shukko",
        instruction="出張申請",
        fields={"dest": "大阪", "proj_hint": "P-001"},
        status="submitted",
    )
    platform_db.add(task)
    platform_db.commit()

    execution = Execution(
        task_id=task.id,
        attempt_no=1,
        status="submitted",
        final_screen="submitted",
        trip_id=42,
        trip_created=True,
        executed_steps=11,
        errors=["screen:None"],
        correction_candidate={"screen": "confirm", "replan_count": 2},
    )
    platform_db.add(execution)
    platform_db.commit()

    with SessionLocal() as readback:
        loaded_task = readback.get(Task, task.id)
        assert loaded_task.dedup_key == "task:abc"
        assert loaded_task.fields == {"dest": "大阪", "proj_hint": "P-001"}
        assert loaded_task.status == "submitted"
        assert loaded_task.created_at is not None
        assert loaded_task.updated_at is not None

        loaded_exec = readback.get(Execution, execution.id)
        assert loaded_exec.task_id == task.id
        assert loaded_exec.attempt_no == 1
        assert loaded_exec.trip_created is True
        assert loaded_exec.executed_steps == 11
        assert loaded_exec.errors == ["screen:None"]
        assert loaded_exec.correction_candidate == {"screen": "confirm", "replan_count": 2}
        assert loaded_exec.started_at is not None
        assert loaded_exec.finished_at is None


def test_dedup_key_unique_conflicts(platform_db):
    platform_db.add(Task(dedup_key="task:dup", workflow="shukko", instruction="a", fields={}, status="pending"))
    platform_db.commit()
    platform_db.add(Task(dedup_key="task:dup", workflow="shukko", instruction="b", fields={}, status="pending"))
    with pytest.raises(IntegrityError):
        platform_db.commit()


def test_null_dedup_key_allows_multiple(platform_db):
    platform_db.add(Task(dedup_key=None, workflow="shukko", instruction="a", fields={}, status="pending"))
    platform_db.add(Task(dedup_key=None, workflow="shukko", instruction="b", fields={}, status="pending"))
    platform_db.commit()
    count = platform_db.scalar(select(func.count()).select_from(Task).where(Task.dedup_key.is_(None)))
    assert count == 2


def test_delete_task_cascades_executions(platform_db):
    task = Task(dedup_key="task:cascade", workflow="shukko", instruction="a", fields={}, status="failed")
    platform_db.add(task)
    platform_db.commit()
    platform_db.add(Execution(task_id=task.id, attempt_no=1, status="rolled_back", executed_steps=3))
    platform_db.commit()
    task_id = task.id

    platform_db.execute(delete(Task).where(Task.id == task_id))
    platform_db.commit()

    remaining = platform_db.scalar(
        select(func.count()).select_from(Execution).where(Execution.task_id == task_id)
    )
    assert remaining == 0


def test_attempt_no_unique_per_task(platform_db):
    task = Task(dedup_key="task:attempts", workflow="shukko", instruction="a", fields={}, status="running")
    platform_db.add(task)
    platform_db.commit()
    platform_db.add(Execution(task_id=task.id, attempt_no=1, status="verify_failed", executed_steps=5))
    platform_db.commit()
    platform_db.add(Execution(task_id=task.id, attempt_no=1, status="rolled_back", executed_steps=5))
    with pytest.raises(IntegrityError):
        platform_db.commit()


def test_indexes_present():
    inspector = inspect(engine)
    task_indexed = [index["column_names"] for index in inspector.get_indexes("tasks")]
    exec_indexed = [index["column_names"] for index in inspector.get_indexes("executions")]
    assert ["dedup_key"] in task_indexed
    assert ["task_id"] in exec_indexed


def test_migration_downgrade_then_upgrade_is_clean():
    config = _alembic_config()
    command.downgrade(config, "0002")
    inspector = inspect(engine)
    assert not inspector.has_table("tasks")
    assert not inspector.has_table("executions")

    command.upgrade(config, "0003")
    inspector = inspect(engine)
    assert inspector.has_table("tasks")
    assert inspector.has_table("executions")
