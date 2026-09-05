import os
from pathlib import Path

from fastapi.testclient import TestClient

import app.config as config
from app import db
from app.db import clear_memory
from app.main import app

KEY = "dev-key"
TENANT = "00000000-0000-0000-0000-000000000001"
FIX = str(Path(__file__).parent.parent.parent.parent
          / "workers" / "indexer" / "tests" / "fixtures" / "demo-repo")


def setup_function(_):
    clear_memory()
    config.API_KEYS.setdefault(KEY, TENANT)
    for v in ("PIL_INDEX_ROOT", "PIL_GRAPH_ROOT", "PIL_ADMIN_KEY",
              "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"):
        os.environ.pop(v, None)


def _admin():
    os.environ["PIL_ADMIN_KEY"] = "secret-admin"
    return {"X-Admin-Key": "secret-admin"}


def test_billing_status_default_free():
    c = TestClient(app)
    body = c.get("/v1/billing/status", headers={"X-API-Key": KEY}).json()
    assert body["plan"] == "free"
    assert body["quotas"]["feedback"]["limit"] == 500


def test_quota_429_with_upgrade_hint():
    c = TestClient(app)
    for _ in range(500):
        db.usage_bump(TENANT, "feedback")
    r = c.post("/v1/feedback", headers={"X-API-Key": KEY},
               json={"title": "one too many"})
    assert r.status_code == 429, r.text
    assert "Upgrade" in r.json()["detail"]["error"]


def test_admin_plan_upgrade_restores_access():
    c = TestClient(app)
    assert c.post("/v1/admin/plan", headers=_admin(),
                  json={"tenant_id": TENANT, "plan": "pro"}).status_code == 200
    assert c.get("/v1/billing/status", headers={"X-API-Key": KEY}).json()["plan"] == "pro"
    for _ in range(500):
        db.usage_bump(TENANT, "feedback")
    r = c.post("/v1/feedback", headers={"X-API-Key": KEY}, json={"title": "ok now"})
    assert r.status_code == 202, r.text


def test_admin_guard_and_plan_validation():
    c = TestClient(app)
    assert c.post("/v1/admin/plan", json={"tenant_id": TENANT, "plan": "pro"}).status_code == 403
    assert c.post("/v1/admin/plan", headers=_admin(),
                  json={"tenant_id": TENANT, "plan": "diamond"}).status_code == 422


def test_checkout_and_stripe_webhook_need_config():
    c = TestClient(app)
    r = c.post("/v1/billing/checkout", headers={"X-API-Key": KEY},
               json={"plan": "pro"})
    assert r.status_code == 501 and "STRIPE_SECRET_KEY" in r.text
    r2 = c.post("/v1/webhooks/stripe", json={"type": "x"})
    assert r2.status_code == 501


def test_purge_removes_all_tenant_data(tmp_path, monkeypatch):
    idx = tmp_path / "idx"
    monkeypatch.setenv("PIL_INDEX_ROOT", str(idx))
    monkeypatch.setenv("PIL_GRAPH_ROOT", str(tmp_path / "g"))
    c = TestClient(app)
    c.post("/v1/repos/sync", headers={"X-API-Key": KEY},
           json={"repo_url": FIX, "alias": "demo"})
    c.post("/v1/feedback", headers={"X-API-Key": KEY}, json={"title": "keep me"})
    c.post("/v1/deploys", headers={"X-API-Key": KEY},
           json={"service": "s", "version": "1"})
    c.post("/v1/clusters/rebuild", headers={"X-API-Key": KEY})
    c.post("/v1/graph/rebuild", headers={"X-API-Key": KEY})

    assert c.delete(f"/v1/admin/tenants/{TENANT}").status_code == 403
    r = c.delete(f"/v1/admin/tenants/{TENANT}", headers=_admin())
    assert r.status_code == 200, r.text

    assert c.get("/v1/feedback", headers={"X-API-Key": KEY}).json()["items"] == []
    assert c.get("/v1/deploys", headers={"X-API-Key": KEY}).json()["items"] == []
    assert c.get("/v1/clusters", headers={"X-API-Key": KEY}).json()["items"] == []
    assert c.get("/v1/code/search", headers={"X-API-Key": KEY},
                 params={"q": "checkout"}).json()["items"] == []
    assert not (idx / TENANT).exists()
