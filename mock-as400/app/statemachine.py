import datetime as dt
import re

LOGIN = "login"
MENU = "menu"
TRIP_INPUT = "trip_input"
PROJ_PROMPT = "proj_prompt"
CONFIRM = "confirm"
SUBMITTED = "submitted"
ABORTED = "aborted"

FIELD_MAXLEN = {"DEST": 12, "PURPOSE": 20}
REQUIRED_FIELDS = ["DEST", "DEPTDATE", "RETDATE", "DAYS", "PURPOSE", "PROJ"]
PROJ_PATTERN = re.compile(r"^P-\d{3}$")
DATE_PATTERN = re.compile(r"^\d{8}$")
DEFAULT_PREV_PROJ = "P-002"


def initial_state(start_screen=LOGIN):
    return {
        "screen": start_screen,
        "fields": {},
        "prev_proj": DEFAULT_PREV_PROJ,
        "trip_id": None,
        "errors": [],
        "pending_trip": None,
    }


def _set_field(state, target, value):
    text = value if value is not None else ""
    maxlen = FIELD_MAXLEN.get(target)
    if maxlen is not None:
        text = text[:maxlen]
    state["fields"][target] = text


def _validate(fields):
    errors = []
    for name in REQUIRED_FIELDS:
        if not fields.get(name):
            errors.append(f"{name}_required")
    for name in ("DEPTDATE", "RETDATE"):
        value = fields.get(name)
        if value and not DATE_PATTERN.match(value):
            errors.append(f"{name}_format")
    days = fields.get("DAYS")
    if days and not days.isdigit():
        errors.append("DAYS_numeric")
    proj = fields.get("PROJ")
    if proj and not PROJ_PATTERN.match(proj):
        errors.append("PROJ_format")
    return errors


def _to_iso_date(yyyymmdd):
    return dt.date(int(yyyymmdd[0:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8])).isoformat()


def _build_trip_payload(fields):
    return {
        "dest": fields["DEST"],
        "dept_date": _to_iso_date(fields["DEPTDATE"]),
        "ret_date": _to_iso_date(fields["RETDATE"]),
        "days": int(fields["DAYS"]),
        "purpose": fields["PURPOSE"],
        "proj": fields["PROJ"],
        "overseas": fields.get("OVRSEA") == "Y",
    }


def apply_step(state, step):
    new_state = {**state, "errors": [], "fields": dict(state["fields"])}
    screen = new_state["screen"]
    stype = step.get("type")
    key = step.get("key")
    target = step.get("target")
    value = step.get("value")

    if screen in (SUBMITTED, ABORTED):
        new_state["errors"] = [f"session_closed:{screen}"]
        return new_state

    if screen == LOGIN:
        if stype == "nav" and key == "Enter":
            new_state["screen"] = MENU
        else:
            new_state["errors"] = ["invalid_on_login"]
        return new_state

    if screen == MENU:
        if stype == "nav" and key == "Enter":
            new_state["screen"] = TRIP_INPUT
        elif stype == "fkey" and key == "F3":
            new_state["screen"] = ABORTED
        else:
            new_state["errors"] = ["invalid_on_menu"]
        return new_state

    if screen == TRIP_INPUT:
        if stype == "field":
            _set_field(new_state, target, value)
        elif stype == "fkey" and key == "F4":
            new_state["screen"] = PROJ_PROMPT
        elif stype == "fkey" and key == "F9":
            new_state["fields"]["PROJ"] = new_state["prev_proj"]
        elif stype == "fkey" and key in ("Tab", "FieldExit"):
            pass
        elif stype == "fkey" and key == "F3":
            new_state["screen"] = ABORTED
        elif stype in ("fkey", "nav") and key == "Enter":
            errors = _validate(new_state["fields"])
            if errors:
                new_state["errors"] = errors
            else:
                new_state["screen"] = CONFIRM
        else:
            new_state["errors"] = [f"invalid_on_trip_input:{key}"]
        return new_state

    if screen == PROJ_PROMPT:
        if stype == "field" and target == "PROJ":
            _set_field(new_state, "PROJ", value)
            new_state["screen"] = TRIP_INPUT
        elif stype == "fkey" and key == "F3":
            new_state["screen"] = TRIP_INPUT
        elif stype in ("fkey", "nav") and key == "Enter":
            new_state["screen"] = TRIP_INPUT
        else:
            new_state["errors"] = [f"invalid_on_proj_prompt:{key}"]
        return new_state

    if screen == CONFIRM:
        if stype in ("fkey", "nav") and key == "Enter":
            new_state["pending_trip"] = _build_trip_payload(new_state["fields"])
            new_state["screen"] = SUBMITTED
        elif stype == "fkey" and key == "F3":
            new_state["screen"] = TRIP_INPUT
        else:
            new_state["errors"] = [f"invalid_on_confirm:{key}"]
        return new_state

    new_state["errors"] = [f"unknown_screen:{screen}"]
    return new_state
