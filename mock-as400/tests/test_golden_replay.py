import json
from pathlib import Path

import pytest

from app import statemachine as sm
from app.repositories import trip_repo
from app.services import session_service

CASES = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "cases.json").read_text(encoding="utf-8")
)["cases"]


def _last_field(golden, target):
    value = None
    for step in golden:
        if step.get("type") == "field" and step.get("target") == target:
            value = step.get("value")
    return value


def _replay(db, golden):
    record = session_service.start(db, start_screen=sm.MENU)
    for step in golden:
        record = session_service.step(db, record.id, step)
    return record


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_golden_replay(case, db):
    golden = case["golden"]
    cid = case["case_id"]
    record = _replay(db, golden)

    if cid == "case_04_edge_empty_required":
        assert record.screen == sm.ABORTED
        assert record.trip_id is None
        assert trip_repo.list_all(db) is not None
        return

    assert record.screen == sm.SUBMITTED
    assert record.trip_id is not None
    trip = trip_repo.get(db, record.trip_id)
    try:
        assert trip.dest == _last_field(golden, "DEST")
        assert trip.proj == _last_field(golden, "PROJ")
        assert trip.purpose == _last_field(golden, "PURPOSE")
        assert str(trip.days) == _last_field(golden, "DAYS")
        assert trip.dept_date.strftime("%Y%m%d") == _last_field(golden, "DEPTDATE")
        assert trip.ret_date.strftime("%Y%m%d") == _last_field(golden, "RETDATE")
        assert trip.overseas == (_last_field(golden, "OVRSEA") == "Y")

        if cid == "case_03_edge_branch_overseas":
            assert trip.overseas is True
        if cid == "case_05_edge_invalid_proj":
            assert trip.proj == "P-002"
        if cid == "case_06_edge_long_purpose":
            assert len(trip.purpose) == 20
        if cid == "case_07_edge_reuse_prev":
            assert trip.proj == sm.DEFAULT_PREV_PROJ
        if cid == "case_08_edge_days_recalc":
            assert trip.days == 4
    finally:
        trip_repo.delete(db, record.trip_id)


def test_all_eight_cases_present():
    assert len(CASES) == 8
