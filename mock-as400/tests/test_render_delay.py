import time


def _start(client):
    return client.post("/session").json()["session_id"]


def _step(client, sid, type, key=None, target=None, value=None):
    payload = {"type": type, "target": target, "value": value, "key": key}
    return client.post(f"/session/{sid}/step", json=payload).json()


def test_default_transition_is_immediate_and_ready(client):
    sid = _start(client)
    body = _step(client, sid, "nav", key="Enter")
    assert body["screen"] == "menu"
    assert body["ready"] is True


def test_render_delay_holds_old_screen_then_settles(client, monkeypatch):
    monkeypatch.setenv("MOCK_AS400_RENDER_DELAY_MS", "400")
    sid = _start(client)

    busy = _step(client, sid, "nav", key="Enter")
    assert busy["screen"] == "login"
    assert busy["ready"] is False

    immediate = client.get(f"/session/{sid}").json()
    assert immediate["screen"] == "login"
    assert immediate["ready"] is False

    deadline = time.monotonic() + 5.0
    settled = immediate
    while time.monotonic() < deadline:
        settled = client.get(f"/session/{sid}").json()
        if settled["ready"]:
            break
        time.sleep(0.02)
    assert settled["ready"] is True
    assert settled["screen"] == "menu"


def test_render_delay_inhibits_input_until_ready(client, monkeypatch):
    monkeypatch.setenv("MOCK_AS400_RENDER_DELAY_MS", "400")
    sid = _start(client)
    _step(client, sid, "nav", key="Enter")
    dropped = _step(client, sid, "nav", key="Enter")
    assert dropped["ready"] is False
    assert dropped["screen"] == "login"
