from sqlalchemy import func, select

from app.models import TripApplication
from app.repositories import trip_repo
from app.schemas import TripApplicationCreate


def _payload() -> TripApplicationCreate:
    return TripApplicationCreate(
        dest="OSAKA",
        dept_date="2026-06-10",
        ret_date="2026-06-11",
        days=2,
        purpose="製品X納入調整",
        proj="P-001",
    )


def _count(db) -> int:
    return db.scalar(select(func.count()).select_from(TripApplication))


def test_null_key_never_dedups(db):
    trip_repo.create_idempotent(db, _payload(), None)
    trip_repo.create_idempotent(db, _payload(), None)
    assert _count(db) == 2


def test_same_key_returns_existing_without_insert(db):
    winner, created_first = trip_repo.create_idempotent(db, _payload(), "key-1")
    duplicate, created_second = trip_repo.create_idempotent(db, _payload(), "key-1")
    assert created_first is True
    assert created_second is False
    assert duplicate.id == winner.id
    assert _count(db) == 1


def test_integrity_error_fallback_refetches_winner(db, monkeypatch):
    winner, created_first = trip_repo.create_idempotent(db, _payload(), "race-key")
    assert created_first is True

    real_by_key = trip_repo._by_key
    calls = {"n": 0}

    def flaky_by_key(session, key):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return real_by_key(session, key)

    monkeypatch.setattr(trip_repo, "_by_key", flaky_by_key)
    trip, created = trip_repo.create_idempotent(db, _payload(), "race-key")
    assert created is False
    assert trip.id == winner.id
    assert calls["n"] == 2
    assert _count(db) == 1
