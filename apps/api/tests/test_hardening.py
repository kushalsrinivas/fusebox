import os

from fastapi.testclient import TestClient

import app.config as config
from app.db import clear_memory
from app.main import app

KEY = "dev-key"


def setup_function(_):
    clear_memory()
    config.API_KEYS.setdefault(KEY, "00000000-0000-0000-0000-000000000001")
    os.environ.pop("PIL_RATE_LIMIT", None)


def test_middleware_429_and_headers(monkeypatch):
    monkeypatch.setenv("PIL_RATE_LIMIT", "3")
    c = TestClient(app)
    codes = [c.get("/v1/feedback", headers={"X-API-Key": KEY}).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200], codes
    assert codes[3:] == [429, 429], codes
    assert "rate limited" in c.get("/v1/feedback", headers={"X-API-Key": KEY}).text


def test_healthz_skips_rate_limit(monkeypatch):
    monkeypatch.setenv("PIL_RATE_LIMIT", "1")
    c = TestClient(app)
    assert c.get("/healthz").status_code == 200
    assert c.get("/healthz").status_code == 200


def test_audit_records_approvals():
    c = TestClient(app)
    c.post("/v1/onboarding/demo", headers={"X-API-Key": KEY})
    items = c.get("/v1/audit", headers={"X-API-Key": KEY}).json()["items"]
    assert any(a["action"] == "demo_seeded" for a in items), items
