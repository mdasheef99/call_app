"""Foundation endpoint tests — no DB, no network, no voice."""

from fastapi.testclient import TestClient

from app.main import APP_NAME, APP_VERSION, app

client = TestClient(app)


def test_health_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == APP_NAME
    assert body["version"] == APP_VERSION


def test_status_reports_foundation_scope():
    resp = client.get("/v1/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["app"] == APP_NAME
    assert body["scope"] == "foundation-only"
    assert body["voice_enabled"] is False
    assert body["database_enabled"] is False
    assert body["auth_enabled"] is False
    assert "server_time_utc" in body
    assert "python" in body


def test_health_allows_local_web_preview_origin():
    resp = client.get("/health", headers={"Origin": "http://localhost:8081"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:8081"
