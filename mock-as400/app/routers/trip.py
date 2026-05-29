from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import trip_repo
from app.schemas import TripApplicationCreate, TripApplicationRead

router = APIRouter(prefix="/trip", tags=["trip"])


@router.post("", response_model=TripApplicationRead, status_code=status.HTTP_201_CREATED)
def create_trip(payload: TripApplicationCreate, db: Session = Depends(get_db)) -> TripApplicationRead:
    return TripApplicationRead.model_validate(trip_repo.create(db, payload))


@router.get("/{trip_id}", response_model=TripApplicationRead)
def get_trip(trip_id: int, db: Session = Depends(get_db)) -> TripApplicationRead:
    record = trip_repo.get(db, trip_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trip_application not found")
    return TripApplicationRead.model_validate(record)
