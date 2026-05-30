from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import TripApplication
from app.schemas import TripApplicationCreate


def create(db: Session, data: TripApplicationCreate) -> TripApplication:
    record = TripApplication(**data.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _by_key(db: Session, key: str) -> TripApplication | None:
    return db.scalar(select(TripApplication).where(TripApplication.idempotency_key == key))


def create_idempotent(
    db: Session, data: TripApplicationCreate, key: str | None
) -> tuple[TripApplication, bool]:
    if key is None:
        return create(db, data), True

    existing = _by_key(db, key)
    if existing is not None:
        return existing, False

    record = TripApplication(**data.model_dump(), idempotency_key=key)
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _by_key(db, key), False
    db.refresh(record)
    return record, True


def get(db: Session, trip_id: int) -> TripApplication | None:
    return db.get(TripApplication, trip_id)


def latest_proj(db: Session) -> str | None:
    return db.scalar(select(TripApplication.proj).order_by(TripApplication.id.desc()).limit(1))


def list_all(db: Session) -> list[TripApplication]:
    return list(db.scalars(select(TripApplication)))


def delete(db: Session, trip_id: int) -> None:
    record = db.get(TripApplication, trip_id)
    if record is not None:
        db.delete(record)
        db.commit()
