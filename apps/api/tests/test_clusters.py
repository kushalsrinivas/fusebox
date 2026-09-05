import os
from pathlib import Path

from fastapi.testclient import TestClient

import app.config as config
from app.db import clear_memory
from app.main import app

KEY = "dev-key"
FIX = str(Path(__file__).parent.parent.parent.parent
          / "workers" / "indexer" / "tests" / "fixtures" / "demo-repo")


def setup_function(_):
    clear_memory()
    config.API_KEYS.setdefault(KEY, "00000000-0000-0000-0000-000000000001")
    os.environ.pop("PIL_INDEX_ROOT", None)
    os.environ.pop("PIL_GRAPH_ROOT", None)


def _seed(tmp_path, monkeypatch):
    idx = str(tmp_path / "idx")
    monkeypatch.setenv("PIL_INDEX_ROOT", idx)
    monkeypatch.setenv("PIL_GRAPH_ROOT", str(tmp_path / "g"))
    c = TestClient(app)
    c.post("/v1/repos/sync", headers={"X-API-Key": KEY},
           json={"repo_url": FIX, "alias": "demo"})
    for i, (title, body) in enumerate([
            ("checkout crash when tapping pay", "tap pay, app closes on ios"),
            ("checkout crash on tap pay button", "closes every time on pay"),
            ("checkout crash tapping pay", "pay screen crash ios 17"),
            ("dark mode please", "oled night display for reading")]):
        c.post("/v1/feedback", headers={"X-API-Key": KEY},
               json={"title": f"{title} #{i}", "body": body,
                     "service_hint": "payments-api" if i < 3 else None})
    c.post("/v1/deploys", headers={"X-API-Key": KEY},
           json={"service": "payments-api", "version": "1.4.3",
                 "commit_sha": "ab12", "deployed_at": "2026-09-05T10:00:00Z"})
    c.post("/v1/webhooks/sentry", headers={"X-API-Key": KEY},
           json={"title": "capture failed: timeout", "project_slug": "payments-api",
                 "event": {"culprit": "checkout.charge",
                           "datetime": "2026-09-05T12:00:00Z"}})
    return c


def test_rebuild_groups_and_detail(tmp_path, monkeypatch):
    c = _seed(tmp_path, monkeypatch)
    r = c.post("/v1/clusters/rebuild", headers={"X-API-Key": KEY})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 2, items
    big = max(items, key=lambda x: x["count"])
    assert big["count"] == 3 and big["service_hint"] == "payments-api"

    d = c.get(f"/v1/clusters/{big['id']}", headers={"X-API-Key": KEY})
    assert d.status_code == 200
    assert len(d.json()["members"]) == 3


def test_investigate_full_loop_names_commit(tmp_path, monkeypatch):
    c = _seed(tmp_path, monkeypatch)
    big = max(c.post("/v1/clusters/rebuild", headers={"X-API-Key": KEY}).json()["items"],
              key=lambda x: x["count"])
    r = c.post(f"/v1/clusters/{big['id']}/investigate", headers={"X-API-Key": KEY})
    assert r.status_code == 200, r.text
    body = r.json()
    res = body["result"]
    assert res["status"] == "hypothesized"
    top = res["hypotheses"][0]
    assert top["commit_sha"] == "ab12", top
    cites = " ".join(top["citations"])
    assert "index://demo/" in cites and "pil://deployments/" in cites and "pil://errors/" in cites
    assert res["repro_steps"], "expected repro steps"
    kinds = [e["kind"] for e in body["timeline"]]
    assert {"report", "error", "deploy", "code"} <= set(kinds), kinds
    # persisted + served back
    d = c.get(f"/v1/clusters/{big['id']}", headers={"X-API-Key": KEY})
    assert d.json()["investigation"]["id"] == body["investigation_id"]


def test_investigate_feature_request_needs_info(tmp_path, monkeypatch):
    c = _seed(tmp_path, monkeypatch)
    small = min(c.post("/v1/clusters/rebuild", headers={"X-API-Key": KEY}).json()["items"],
                key=lambda x: x["count"])
    r = c.post(f"/v1/clusters/{small['id']}/investigate", headers={"X-API-Key": KEY})
    assert r.json()["result"]["status"] == "needs_info"


def test_graph_rebuild_and_timeline(tmp_path, monkeypatch):
    c = _seed(tmp_path, monkeypatch)
    c.post("/v1/clusters/rebuild", headers={"X-API-Key": KEY})
    r = c.post("/v1/graph/rebuild", headers={"X-API-Key": KEY})
    assert r.status_code == 200 and r.json()["nodes"] > 5
    big = max(c.get("/v1/clusters", headers={"X-API-Key": KEY}).json()["items"],
              key=lambda x: x["count"])
    t = c.get("/v1/graph/timeline", headers={"X-API-Key": KEY},
              params={"cluster_key": big["key"]})
    assert t.status_code == 200 and len(t.json()["items"]) >= 4
