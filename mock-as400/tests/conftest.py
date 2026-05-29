from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db import SessionLocal
from app.main import app
from app.models import MockSession, TripApplication

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def _clean_tables() -> None:
    with SessionLocal() as session:
        session.execute(delete(MockSession))
        session.execute(delete(TripApplication))
        session.commit()


@pytest.fixture(scope="session", autouse=True)
def setup_schema():
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    command.upgrade(config, "head")
    yield


@pytest.fixture
def client():
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        _clean_tables()


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(delete(MockSession))
        session.execute(delete(TripApplication))
        session.commit()
        session.close()
