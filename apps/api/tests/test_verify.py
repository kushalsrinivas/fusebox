from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import app.config as config
from app import db
from app.db import clear_memory
from app.main import app

KEY = "dev-key"
TENANT = "00000000-0000-0000-0000-000000000001"


def setup_function(_):
    clear_memory()
    config.API_KEYS.setdefault(KEY, TENANT)


def _iso(dt):
    return dt.isoformat()


def _sentry(c, title, ts, fp):
    return c.post("/v1/webhooks/sentry", headers={"X-API-Key": KEY},
                  json={"title": title, "project_slug": "payments-api",
                        "event": {"culprit": "checkout.charge", "datetime": ts,
                                  "fingerprint": "x"},
                        "fingerprint": fp})


def _action_with_fp(fp, created_at):
    cid = db.replace_clusters(TENANT, [
        {"key": "c_0", "title": "crash", "members": [], "count": 1}])[0]["id"]
    inv = db.save_investigation(TENANT, cid, {
        "status": "hypothesized", "severity": 4, "confidence": 0.9,
        "hypotheses": [{"title": "h", "citations": [f"pil://errors/{fp}"],
                        "deployment": None, "commit_sha": None}],
        "repro_steps": []})
    row = db.save_action(TENANT, {
        "cluster_id": cid, "investigation_id": inv["id"], "repo": "demo",
        "branch": "fuse/c_0-x", "title": "t", "diff": "d",
        "status": "approved", "risk": {}, "sandbox": {}, "dry_run": True})
    row["created_at"] = created_at
    return row


def test_verify_fixed_when_errors_stop():
    c = TestClient(app)
    now = datetime.now(timezone.utc)
    created = now - timedelta(hours=100)
    for i in range(5):
        _sentry(c, "capture failed", _iso(created - timedelta(hours=20 - i)), "fp-fixed")
    row = _action_with_fp("fp-fixed", _iso(created))
    r = c.post(f"/v1/actions/{row['id']}/verify", headers={"X-API-Key": KEY},
               params={"window_h": 48})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "verified_fixed", body
    assert body["groups"][0]["before"] == 5 and body["groups"][0]["after"] == 0
    assert c.get("/v1/verifications", headers={"X-API-Key": KEY}).json()["items"]


def test_verify_regressed_on_growth():
    c = TestClient(app)
    now = datetime.now(timezone.utc)
    created = now - timedelta(hours=100)
    for i in range(2):
        _sentry(c, "capture failed", _iso(created - timedelta(hours=20 - i)), "fp-reg")
    row = _action_with_fp("fp-reg", _iso(created))
    for i in range(10):
        _sentry(c, "capture failed", _iso(created + timedelta(hours=10, minutes=i)), "fp-reg")
    r = c.post(f"/v1/actions/{row['id']}/verify", headers={"X-API-Key": KEY},
               params={"window_h": 48})
    assert r.json()["status"] == "regressed", r.text


def test_verify_too_early_inconclusive():
    c = TestClient(app)
    now = datetime.now(timezone.utc)
    _sentry(c, "capture failed", _iso(now - timedelta(hours=2)), "fp-early")
    row = _action_with_fp("fp-early", _iso(now - timedelta(hours=1)))
    r = c.post(f"/v1/actions/{row['id']}/verify", headers={"X-API-Key": KEY})
    body = r.json()
    assert body["status"] == "inconclusive" and body["groups"][0]["delta"] is None


def test_verify_requires_approved_action():
    c = TestClient(app)
    row = db.save_action(TENANT, {
        "cluster_id": None, "investigation_id": None, "repo": "demo",
        "branch": "", "title": "t", "diff": "d", "status": "sandbox_failed",
        "risk": {}, "sandbox": {}, "dry_run": True})
    r = c.post(f"/v1/actions/{row['id']}/verify", headers={"X-API-Key": KEY})
    assert r.status_code == 422
