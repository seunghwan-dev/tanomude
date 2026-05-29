import uuid

from sqlalchemy.orm import Session

from app.models import MockSession


def create(db: Session, screen: str, payload: dict) -> MockSession:
    record = MockSession(id=str(uuid.uuid4()), screen=screen, payload=payload, trip_id=None)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get(db: Session, session_id: str) -> MockSession | None:
    return db.get(MockSession, session_id)


def save(db: Session, record: MockSession, screen: str, payload: dict, trip_id: int | None) -> MockSession:
    record.screen = screen
    record.payload = payload
    record.trip_id = trip_id
    db.commit()
    db.refresh(record)
    return record
