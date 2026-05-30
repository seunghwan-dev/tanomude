import time

from app.db import SessionLocal
from app.models import MockSession
from app.services.session_service import _PENDING


def _start(client):
    return client.post("/session").json()["session_id"]


def _step(client, sid, type, key=None, target=None, value=None):
    payload = {"type": type, "target": target, "value": value, "key": key}
    return client.post(f"/session/{sid}/step", json=payload).json()


def _db_row(sid):
    with SessionLocal() as db:
        row = db.get(MockSession, sid)
        return row.screen, dict(row.payload)


def test_get_settles_view_without_persisting(client, monkeypatch):
    monkeypatch.setenv("MOCK_AS400_RENDER_DELAY_MS", "50")
    sid = _start(client)
    _step(client, sid, "nav", key="Enter")

    held_screen, held_payload = _db_row(sid)
    assert held_screen == "login"
    assert held_payload.get(_PENDING) is not None

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if client.get(f"/session/{sid}").json()["ready"]:
            break
        time.sleep(0.02)

    views = [client.get(f"/session/{sid}").json() for _ in range(5)]
    assert all(view["ready"] and view["screen"] == "menu" for view in views)

    after_screen, after_payload = _db_row(sid)
    assert after_screen == "login"
    assert after_payload.get(_PENDING) is not None
