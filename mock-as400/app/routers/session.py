from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import MockSession
from app.schemas import SessionCreate, SessionStateOut, StepIn
from app.services import session_service

router = APIRouter(prefix="/session", tags=["session"])


def _to_out(record: MockSession) -> SessionStateOut:
    payload = record.payload
    return SessionStateOut(
        session_id=record.id,
        screen=record.screen,
        fields=payload.get("fields", {}),
        errors=payload.get("errors", []),
        trip_id=record.trip_id,
        ready=session_service.is_ready(record),
        trip_created=payload.get("trip_created"),
    )


@router.post("", response_model=SessionStateOut, status_code=status.HTTP_201_CREATED)
def create_session(body: SessionCreate | None = None, db: Session = Depends(get_db)) -> SessionStateOut:
    key = body.idempotency_key if body is not None else None
    return _to_out(session_service.start(db, idempotency_key=key))


@router.post("/{session_id}/step", response_model=SessionStateOut)
def send_step(session_id: str, step: StepIn, db: Session = Depends(get_db)) -> SessionStateOut:
    record = session_service.step(db, session_id, step.model_dump())
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return _to_out(record)


@router.get("/{session_id}", response_model=SessionStateOut)
def get_session(session_id: str, db: Session = Depends(get_db)) -> SessionStateOut:
    record = session_service.read(db, session_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return _to_out(record)
