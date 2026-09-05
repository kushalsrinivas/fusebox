import os
from pathlib import Path

from fastapi.testclient import TestClient

import app.config as config
from app.db import clear_memory
from app.main import app

KEY = "dev-key"
FIX = str(Path(__file__).parent.parent.parent.parent
          / "workers" / "indexer" / "tests" / "fixtures" / "demo-repo")

GOOD_DIFF = """--- a/apps/payments/checkout.py
+++ b/apps/payments/checkout.py
@@ -8,3 +8,4 @@
 def charge(order_id: str, card_token: str, amount_cents: int) -> dict:
     auth = _gateway.authorize(card_token, amount_cents)
-    receipt = _gateway.capture(auth["auth_id"])
+    receipt = _gateway.capture(auth["auth_id"], timeout_ms=5000)
     return {"order_id": order_id, "receipt_id": receipt["id"]}
"""


def setup_function(_):
    clear_memory()
    config.API_KEYS.setdefault(KEY, "00000000-0000-0000-0000-000000000001")
    os.environ.pop("PIL_INDEX_ROOT", None)
    os.environ.pop("PIL_GRAPH_ROOT", None)
    os.environ.pop("PIL_GITHUB_TOKEN", None)


def _full_loop(tmp_path, monkeypatch):
    monkeypatch.setenv("PIL_INDEX_ROOT", str(tmp_path / "idx"))
    monkeypatch.setenv("PIL_GRAPH_ROOT", str(tmp_path / "g"))
    c = TestClient(app)
    c.post("/v1/repos/sync", headers={"X-API-Key": KEY},
           json={"repo_url": FIX, "alias": "demo"})
    for i in range(3):
        c.post("/v1/feedback", headers={"X-API-Key": KEY},
               json={"title": f"checkout crash tapping pay #{i}",
                     "body": "tap pay app closes", "service_hint": "payments-api"})
    c.post("/v1/deploys", headers={"X-API-Key": KEY},
           json={"service": "payments-api", "version": "1.4.3",
                 "commit_sha": "ab12", "deployed_at": "2026-09-05T10:00:00Z"})
    c.post("/v1/webhooks/sentry", headers={"X-API-Key": KEY},
           json={"title": "capture failed: timeout", "project_slug": "payments-api",
                 "event": {"culprit": "checkout.charge",
                           "datetime": "2026-09-05T12:00:00Z"}})
    big = max(c.post("/v1/clusters/rebuild", headers={"X-API-Key": KEY}).json()["items"],
              key=lambda x: x["count"])
    c.post(f"/v1/clusters/{big['id']}/investigate", headers={"X-API-Key": KEY})
    return c, big


def test_propose_clean_diff_sandbox_passes(tmp_path, monkeypatch):
    c, big = _full_loop(tmp_path, monkeypatch)
    r = c.post("/v1/actions/propose", headers={"X-API-Key": KEY},
               json={"cluster_id": big["id"], "repo": "demo", "diff": GOOD_DIFF})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["action"]["status"] == "sandbox_passed", body
    assert body["sandbox"]["ok"] is True
    assert body["risk"]["level"] in ("low", "medium", "high")
    assert body["action"]["branch"].startswith("fuse/")


def test_propose_denylisted_rejected_and_audited(tmp_path, monkeypatch):
    c, big = _full_loop(tmp_path, monkeypatch)
    bad = GOOD_DIFF.replace("apps/payments/checkout.py", "auth/login.py")
    r = c.post("/v1/actions/propose", headers={"X-API-Key": KEY},
               json={"cluster_id": big["id"], "repo": "demo", "diff": bad})
    assert r.status_code == 422
    items = c.get("/v1/actions", headers={"X-API-Key": KEY}).json()["items"]
    assert any(a["status"] == "rejected_by_policy" for a in items)


def test_propose_secret_blocked(tmp_path, monkeypatch):
    c, big = _full_loop(tmp_path, monkeypatch)
    bad = GOOD_DIFF + '+token = "sk-abc123XYZ456789"\n'
    r = c.post("/v1/actions/propose", headers={"X-API-Key": KEY},
               json={"cluster_id": big["id"], "repo": "demo", "diff": bad})
    assert r.status_code == 422 and "secret" in r.text.lower()


def test_propose_broken_diff_sandbox_fails(tmp_path, monkeypatch):
    c, big = _full_loop(tmp_path, monkeypatch)
    broken = GOOD_DIFF.replace("+    receipt = _gateway.capture(auth[\"auth_id\"], timeout_ms=5000)",
                               "+    receipt = _gateway.capture((auth[\"auth_id\"]")
    r = c.post("/v1/actions/propose", headers={"X-API-Key": KEY},
               json={"cluster_id": big["id"], "repo": "demo", "diff": broken})
    assert r.status_code == 200, r.text
    assert r.json()["action"]["status"] == "sandbox_failed"
    aid = r.json()["action"]["id"]
    r2 = c.post(f"/v1/actions/{aid}/approve", headers={"X-API-Key": KEY}, json={})
    assert r2.status_code == 422


def test_approve_dry_run_returns_pr_body(tmp_path, monkeypatch):
    c, big = _full_loop(tmp_path, monkeypatch)
    aid = c.post("/v1/actions/propose", headers={"X-API-Key": KEY},
                 json={"cluster_id": big["id"], "repo": "demo",
                       "diff": GOOD_DIFF}).json()["action"]["id"]
    r = c.post(f"/v1/actions/{aid}/approve", headers={"X-API-Key": KEY}, json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["action"]["status"] == "approved"
    assert body["pr"]["dry_run"] is True
    assert body["pr"]["title"].startswith("[Fusebox]")


def test_high_risk_needs_second_confirmation(tmp_path, monkeypatch):
    c, big = _full_loop(tmp_path, monkeypatch)
    monkeypatch.setattr("action.risk.score_risk",
                        lambda *a, **k: {"score": 0.9, "level": "high",
                                         "factors": ["test"], "blast_radius": [],
                                         "requires_two_approvals": True})
    aid = c.post("/v1/actions/propose", headers={"X-API-Key": KEY},
                 json={"cluster_id": big["id"], "repo": "demo",
                       "diff": GOOD_DIFF}).json()["action"]["id"]
    r1 = c.post(f"/v1/actions/{aid}/approve", headers={"X-API-Key": KEY}, json={})
    assert r1.status_code == 422 and "confirm_high_risk" in r1.text
    r2 = c.post(f"/v1/actions/{aid}/approve", headers={"X-API-Key": KEY},
                json={"confirm_high_risk": True})
    assert r2.status_code == 200, r2.text
