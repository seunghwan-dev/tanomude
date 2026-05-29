import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal, engine
from app.main import app
from app.models import Base


@pytest.fixture(scope="session", autouse=True)
def setup_schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
