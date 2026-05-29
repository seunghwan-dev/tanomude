from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete

from backend.db import SessionLocal
from backend.models import KnowledgeChunk, OperationDoc

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def setup_schema():
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    command.upgrade(config, "head")
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.execute(delete(KnowledgeChunk))
        session.execute(delete(OperationDoc))
        session.commit()
        session.close()
