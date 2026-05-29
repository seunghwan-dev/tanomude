from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TripApplication
from app.schemas import TripApplicationCreate


def create(db: Session, data: TripApplicationCreate) -> TripApplication:
    record = TripApplication(**data.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


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
