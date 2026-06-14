from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from backend.agent.app import app, mount_frontend


def _api_app() -> FastAPI:
    api = FastAPI()

    @api.get("/tasks/ping")
    def ping() -> dict:
        return {"ok": True}

    return api


def _build_dist(root):
    dist = root / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>INDEX</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return dist


def test_serves_index_assets_and_spa_fallback(tmp_path):
    api = _api_app()
    mount_frontend(api, _build_dist(tmp_path))
    client = TestClient(api)

    root = client.get("/")
    assert root.status_code == 200
    assert "INDEX" in root.text

    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert "console.log" in asset.text

    fallback = client.get("/some/client/route")
    assert fallback.status_code == 200
    assert "INDEX" in fallback.text

    assert client.get("/tasks/ping").json() == {"ok": True}


def test_unknown_reserved_prefix_paths_return_404(tmp_path):
    api = _api_app()
    mount_frontend(api, _build_dist(tmp_path))
    client = TestClient(api)

    assert client.get("/api/does-not-exist").status_code == 404
    assert client.get("/tasks/does-not-exist").status_code == 404
    assert "INDEX" in client.get("/client/route").text


def test_absent_dist_is_harmless(tmp_path):
    api = _api_app()
    mount_frontend(api, tmp_path / "missing")
    client = TestClient(api)

    assert client.get("/tasks/ping").json() == {"ok": True}
    assert client.get("/").status_code == 404


def test_api_alias_and_original_routes_registered():
    client = TestClient(app)
    assert client.get("/tasks/plan").status_code != status.HTTP_404_NOT_FOUND
    assert client.get("/api/tasks/plan").status_code != status.HTTP_404_NOT_FOUND
    with client.websocket_connect("/ws/agent"):
        pass
