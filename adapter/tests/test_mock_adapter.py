from adapter.mock_adapter import MockAdapter
from adapter.types import AssertSpec, KeyStep


def _field(target, value):
    return KeyStep(type="field", target=target, value=value)


def _fkey(key):
    return KeyStep(type="fkey", key=key)


def _nav(key):
    return KeyStep(type="nav", key=key)


def test_open_and_read_screen(mock_client):
    adapter = MockAdapter(mock_client)
    screen = adapter.open()
    assert screen.session_id is not None
    assert screen.screen == "login"
    assert adapter.read_screen().screen == "login"


def test_send_keys_covers_nav_field_fkey(mock_client):
    adapter = MockAdapter(mock_client)
    adapter.open()
    assert adapter.send_keys(_nav("Enter")).screen == "menu"
    assert adapter.send_keys(_nav("Enter")).screen == "trip_input"
    after_field = adapter.send_keys(_field("DEST", "OSAKA"))
    assert after_field.fields["DEST"] == "OSAKA"
    after_fkey = adapter.send_keys(_fkey("F4"))
    assert after_fkey.screen == "proj_prompt"


def test_assert_state_pass(mock_client):
    adapter = MockAdapter(mock_client)
    adapter.open()
    adapter.send_keys(_nav("Enter"))
    adapter.send_keys(_nav("Enter"))
    adapter.send_keys(_field("DEST", "TOKYO"))
    result = adapter.assert_state(AssertSpec(screen="trip_input", fields={"DEST": "TOKYO"}))
    assert result.ok is True
    assert result.diffs == []


def test_assert_state_fail_reports_diffs(mock_client):
    adapter = MockAdapter(mock_client)
    adapter.open()
    adapter.send_keys(_nav("Enter"))
    adapter.send_keys(_nav("Enter"))
    adapter.send_keys(_field("DEST", "TOKYO"))
    result = adapter.assert_state(AssertSpec(screen="menu", fields={"DEST": "OSAKA"}))
    assert result.ok is False
    screen_diff = next(d for d in result.diffs if d.kind == "screen")
    assert screen_diff.expected == "menu"
    assert screen_diff.actual == "trip_input"
    field_diff = next(d for d in result.diffs if d.kind == "field" and d.key == "DEST")
    assert field_diff.expected == "OSAKA"
    assert field_diff.actual == "TOKYO"


def test_full_flow_assert_trip_saved(mock_client):
    adapter = MockAdapter(mock_client)
    adapter.open()
    sequence = [
        _nav("Enter"),
        _nav("Enter"),
        _field("DEST", "OSAKA"),
        _field("DEPTDATE", "20260610"),
        _field("RETDATE", "20260611"),
        _field("DAYS", "2"),
        _field("PURPOSE", "製品X納入調整"),
        _fkey("F4"),
        _field("PROJ", "P-001"),
        _fkey("Enter"),
        _fkey("Enter"),
    ]
    last = None
    for step in sequence:
        last = adapter.send_keys(step)
    assert last.screen == "submitted"
    result = adapter.assert_state(AssertSpec(screen="submitted", trip_saved=True))
    assert result.ok is True
