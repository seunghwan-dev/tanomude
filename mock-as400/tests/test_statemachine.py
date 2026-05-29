from app import statemachine as sm


def run(steps, start_screen=sm.LOGIN):
    state = sm.initial_state(start_screen)
    for step in steps:
        state = sm.apply_step(state, step)
    return state


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


def test_login_to_menu_to_trip():
    state = run([nav("Enter"), nav("Enter")])
    assert state["screen"] == sm.TRIP_INPUT


def test_happy_path_reaches_submitted_with_payload():
    state = run(HAPPY)
    assert state["screen"] == sm.SUBMITTED
    payload = state["pending_trip"]
    assert payload["dest"] == "OSAKA"
    assert payload["dept_date"] == "2026-06-10"
    assert payload["days"] == 2
    assert payload["proj"] == "P-001"
    assert payload["overseas"] is False


def test_f4_opens_prompt_then_field_returns_to_trip_input():
    state = run([nav("Enter"), nav("Enter"), fkey("F4")])
    assert state["screen"] == sm.PROJ_PROMPT
    state = sm.apply_step(state, field("PROJ", "P-007"))
    assert state["screen"] == sm.TRIP_INPUT
    assert state["fields"]["PROJ"] == "P-007"


def test_purpose_truncated_to_20():
    long_purpose = "実験機B定期点検および部品交換と供給状況確認次期計画打合せ"
    state = run([nav("Enter"), nav("Enter"), field("PURPOSE", long_purpose)])
    assert len(state["fields"]["PURPOSE"]) == 20
    assert state["fields"]["PURPOSE"] == long_purpose[:20]


def test_dest_truncated_to_12():
    state = run([nav("Enter"), nav("Enter"), field("DEST", "VERYLONGCITYNAME")])
    assert state["fields"]["DEST"] == "VERYLONGCITY"


def test_enter_blocks_when_required_missing():
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
    state = run(steps)
    assert state["screen"] == sm.TRIP_INPUT
    assert "DEST_required" in state["errors"]


def test_invalid_proj_format_blocks():
    steps = [
        nav("Enter"),
        nav("Enter"),
        field("DEST", "TOKYO"),
        field("DEPTDATE", "20260622"),
        field("RETDATE", "20260623"),
        field("DAYS", "2"),
        field("PURPOSE", "製品X確認"),
        field("PROJ", "PX-001"),
        fkey("Enter"),
    ]
    state = run(steps)
    assert state["screen"] == sm.TRIP_INPUT
    assert "PROJ_format" in state["errors"]


def test_f3_aborts_from_trip_input():
    state = run([nav("Enter"), nav("Enter"), fkey("F3")])
    assert state["screen"] == sm.ABORTED


def test_overseas_branch_sets_flag():
    steps = [
        nav("Enter"),
        nav("Enter"),
        field("DEST", "SINGAPORE"),
        field("DEPTDATE", "20260615"),
        field("RETDATE", "20260618"),
        field("DAYS", "4"),
        field("PURPOSE", "製品X海外商談"),
        fkey("Tab"),
        field("OVRSEA", "Y"),
        fkey("F4"),
        field("PROJ", "P-003"),
        fkey("Enter"),
        fkey("Enter"),
    ]
    state = run(steps)
    assert state["screen"] == sm.SUBMITTED
    assert state["pending_trip"]["overseas"] is True


def test_f9_recalls_previous_proj():
    state = run([nav("Enter"), nav("Enter"), fkey("F9")])
    assert state["fields"]["PROJ"] == sm.DEFAULT_PREV_PROJ


def test_session_closed_after_submit():
    state = run(HAPPY)
    state = sm.apply_step(state, field("DEST", "KYOTO"))
    assert state["errors"] == ["session_closed:submitted"]
