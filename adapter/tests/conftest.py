from pathlib import Path

import app as app_pkg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db import SessionLocal
from app.main import app
from app.models import MockSession, TripApplication

MOCK_ROOT = Path(app_pkg.__file__).resolve().parent.parent


def _clean_tables() -> None:
    with SessionLocal() as session:
        session.execute(delete(MockSession))
        session.execute(delete(TripApplication))
        session.commit()


@pytest.fixture(scope="session", autouse=True)
def setup_schema():
    config = Config(str(MOCK_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(MOCK_ROOT / "alembic"))
    command.upgrade(config, "head")
    yield


@pytest.fixture
def mock_client():
    client = TestClient(app)
    try:
        yield client
    finally:
        _clean_tables()
