from fastapi.testclient import TestClient

import app.config as config
from app.db import clear_memory
from app.main import app

KEY = "dev-key"
OTHER = "other-key-2"


def setup_function(_):
    clear_memory()
    config.API_KEYS.setdefault(KEY, "00000000-0000-0000-0000-000000000001")
    config.API_KEYS.setdefault(OTHER, "00000000-0000-0000-0000-000000000002")


def test_sentry_webhook_groups_by_fingerprint():
    c = TestClient(app)
    p = {"title": "capture failed: timeout", "project_slug": "payments-api",
         "event": {"culprit": "checkout.charge", "level": "error"}}
    assert c.post("/v1/webhooks/sentry", headers={"X-API-Key": KEY}, json=p).status_code == 202
    assert c.post("/v1/webhooks/sentry", headers={"X-API-Key": KEY}, json=p).status_code == 202
    groups = c.get("/v1/errors/groups", headers={"X-API-Key": KEY}).json()["items"]
    assert len(groups) == 1
    assert groups[0]["count"] == 2
    assert groups[0]["service"] == "payments-api"


def test_error_tenant_isolation():
    c = TestClient(app)
    c.post("/v1/webhooks/sentry", headers={"X-API-Key": KEY},
           json={"title": "boom", "project_slug": "svc"})
    assert c.get("/v1/errors/groups", headers={"X-API-Key": OTHER}).json()["items"] == []


def test_deploy_then_correlate_names_suspect():
    c = TestClient(app)
    c.post("/v1/deploys", headers={"X-API-Key": KEY},
           json={"service": "payments-api", "version": "1.4.2",
                 "commit_sha": "99ff", "deployed_at": "2026-09-04T08:00:00Z"})
    c.post("/v1/deploys", headers={"X-API-Key": KEY},
           json={"service": "payments-api", "version": "1.4.3",
                 "commit_sha": "ab12", "deployed_at": "2026-09-05T10:00:00Z"})
    c.post("/v1/deploys", headers={"X-API-Key": KEY},
           json={"service": "search-api", "version": "9.9",
                 "deployed_at": "2026-09-05T11:00:00Z"})
    r = c.get("/v1/correlate", headers={"X-API-Key": KEY},
              params={"service": "payments-api", "spike_start": "2026-09-05T12:00:00Z"})
    assert r.status_code == 200, r.text
    suspects = r.json()["suspects"]
    assert len(suspects) == 1
    assert suspects[0]["deployment"]["commit_sha"] == "ab12"


def test_correlate_no_deploy_empty():
    c = TestClient(app)
    r = c.get("/v1/correlate", headers={"X-API-Key": KEY},
              params={"service": "nope", "spike_start": "2026-09-05T12:00:00Z"})
    assert r.json()["suspects"] == []
