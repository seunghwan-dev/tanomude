from app.repositories import trip_repo


def field(target, value):
    return {"type": "field", "target": target, "value": value, "key": None}


def fkey(key):
    return {"type": "fkey", "target": None, "value": None, "key": key}


def nav(key):
    return {"type": "nav", "target": None, "value": None, "key": key}


HAPPY = [
    nav("Enter"),
    nav("Enter"),
    field("DEST", "OSAKA"),
    field("DEPTDATE", "20260610"),
    field("RETDATE", "20260611"),
    field("DAYS", "2"),
    field("PURPOSE", "製品X納入調整"),
    fkey("F4"),
    field("PROJ", "P-001"),
    fkey("Enter"),
    fkey("Enter"),
]


def _start(client):
    resp = client.post("/session")
    assert resp.status_code == 201
    return resp.json()["session_id"]


def test_full_flow_persists_and_saves_trip(client, db):
    sid = _start(client)
    last = None
    for step in HAPPY:
        last = client.post(f"/session/{sid}/step", json=step)
        assert last.status_code == 200
    body = last.json()
    assert body["screen"] == "submitted"
    assert body["trip_id"] is not None

    trip_id = body["trip_id"]
    try:
        fetched = client.get(f"/trip/{trip_id}")
        assert fetched.status_code == 200
        assert fetched.json()["dest"] == "OSAKA"
        assert fetched.json()["proj"] == "P-001"

        reloaded = client.get(f"/session/{sid}")
        assert reloaded.json()["screen"] == "submitted"
        assert reloaded.json()["trip_id"] == trip_id
    finally:
        trip_repo.delete(db, trip_id)


def test_abort_flow_saves_no_trip(client):
    sid = _start(client)
    for step in [nav("Enter"), nav("Enter"), fkey("F3")]:
        client.post(f"/session/{sid}/step", json=step)
    state = client.get(f"/session/{sid}").json()
    assert state["screen"] == "aborted"
    assert state["trip_id"] is None


def test_validation_block_keeps_session_on_trip_input(client):
    sid = _start(client)
    steps = [
        nav("Enter"),
        nav("Enter"),
        field("DEPTDATE", "20260620"),
        field("RETDATE", "20260620"),
        field("DAYS", "1"),
        field("PURPOSE", "打ち合わせ"),
        field("PROJ", "P-001"),
        fkey("Enter"),
    ]
    last = None
    for step in steps:
        last = client.post(f"/session/{sid}/step", json=step)
    body = last.json()
    assert body["screen"] == "trip_input"
    assert "DEST_required" in body["errors"]
    assert body["trip_id"] is None
