from app.repositories import trip_repo


def test_trip_application_roundtrip(client, db):
    payload = {
        "dest": "OSAKA",
        "dept_date": "2026-06-10",
        "ret_date": "2026-06-11",
        "days": 2,
        "purpose": "製品X納入調整",
        "proj": "P-001",
        "overseas": False,
    }

    created = client.post("/trip", json=payload)
    assert created.status_code == 201
    trip_id = created.json()["id"]

    try:
        fetched = client.get(f"/trip/{trip_id}")
        assert fetched.status_code == 200
        body = fetched.json()
        assert body["id"] == trip_id
        assert body["dest"] == "OSAKA"
        assert body["dept_date"] == "2026-06-10"
        assert body["ret_date"] == "2026-06-11"
        assert body["days"] == 2
        assert body["purpose"] == "製品X納入調整"
        assert body["proj"] == "P-001"
        assert body["overseas"] is False
        assert body["created_at"]
    finally:
        trip_repo.delete(db, trip_id)


def test_trip_application_overseas_branch_roundtrip(client, db):
    payload = {
        "dest": "SINGAPORE",
        "dept_date": "2026-06-15",
        "ret_date": "2026-06-18",
        "days": 4,
        "purpose": "製品X海外商談",
        "proj": "P-003",
        "overseas": True,
    }

    created = client.post("/trip", json=payload)
    assert created.status_code == 201
    trip_id = created.json()["id"]

    try:
        fetched = client.get(f"/trip/{trip_id}")
        assert fetched.status_code == 200
        assert fetched.json()["overseas"] is True
    finally:
        trip_repo.delete(db, trip_id)
