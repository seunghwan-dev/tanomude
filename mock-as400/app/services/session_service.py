import os
import random
import time

from sqlalchemy.orm import Session

from app import statemachine
from app.models import MockSession
from app.repositories import session_repo, trip_repo
from app.schemas import TripApplicationCreate

RENDER_DELAY_ENV = "MOCK_AS400_RENDER_DELAY_MS"
RENDER_JITTER_ENV = "MOCK_AS400_RENDER_JITTER_MS"
_PENDING = "_pending"
_READY_AT = "_ready_at"


def _render_delay_ms() -> int:
    base = int(os.environ.get(RENDER_DELAY_ENV) or 0)
    jitter = int(os.environ.get(RENDER_JITTER_ENV) or 0)
    if base <= 0 and jitter <= 0:
        return 0
    return base + (random.randint(0, jitter) if jitter > 0 else 0)


def is_ready(record: MockSession) -> bool:
    return record.payload.get(_PENDING) is None


def start(
    db: Session, start_screen: str = statemachine.LOGIN, idempotency_key: str | None = None
) -> MockSession:
    state = statemachine.initial_state(start_screen)
    state["idempotency_key"] = idempotency_key
    last_proj = trip_repo.latest_proj(db)
    if last_proj:
        state["prev_proj"] = last_proj
    return session_repo.create(db, state["screen"], state)


def _settle(db: Session, record: MockSession) -> MockSession:
    pending = record.payload.get(_PENDING)
    if pending is None:
        return record
    if time.time() < record.payload.get(_READY_AT, 0):
        return record
    return session_repo.save(db, record, pending["screen"], pending, pending.get("trip_id"))


def read(db: Session, session_id: str) -> MockSession | None:
    record = session_repo.get(db, session_id)
    if record is None:
        return None
    return _settle(db, record)


def step(db: Session, session_id: str, step_dict: dict) -> MockSession | None:
    record = session_repo.get(db, session_id)
    if record is None:
        return None

    record = _settle(db, record)
    if not is_ready(record):
        return record

    current = record.payload
    state = statemachine.apply_step(dict(current), step_dict)
    trip_id = record.trip_id

    if state["screen"] == statemachine.SUBMITTED and state.get("pending_trip") and trip_id is None:
        trip, created = trip_repo.create_idempotent(
            db, TripApplicationCreate(**state["pending_trip"]), current.get("idempotency_key")
        )
        trip_id = trip.id
        state["trip_id"] = trip_id
        state["trip_created"] = created
        state["pending_trip"] = None

    delay_ms = _render_delay_ms()
    if delay_ms > 0 and state["screen"] != current["screen"]:
        state["trip_id"] = trip_id
        held = {**current, _PENDING: state, _READY_AT: time.time() + delay_ms / 1000.0}
        return session_repo.save(db, record, current["screen"], held, record.trip_id)

    return session_repo.save(db, record, state["screen"], state, trip_id)
