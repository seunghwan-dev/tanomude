from sqlalchemy.orm import Session

from app import statemachine
from app.models import MockSession
from app.repositories import session_repo, trip_repo
from app.schemas import TripApplicationCreate


def start(db: Session, start_screen: str = statemachine.LOGIN) -> MockSession:
    state = statemachine.initial_state(start_screen)
    return session_repo.create(db, state["screen"], state)


def step(db: Session, session_id: str, step_dict: dict) -> MockSession | None:
    record = session_repo.get(db, session_id)
    if record is None:
        return None

    state = statemachine.apply_step(dict(record.payload), step_dict)
    trip_id = record.trip_id

    if state["screen"] == statemachine.SUBMITTED and state.get("pending_trip") and trip_id is None:
        created = trip_repo.create(db, TripApplicationCreate(**state["pending_trip"]))
        trip_id = created.id
        state["trip_id"] = trip_id
        state["pending_trip"] = None

    return session_repo.save(db, record, state["screen"], state, trip_id)
