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


def _seed_feedback(c):
    items = [
        ("dark mode please", "oled night display", "feature_request", None),
        ("oled dark theme", "night reading mode", "feature_request", None),
        ("night mode for app", "dark colors please", "feature_request", None),
        ("checkout crash pay", "tap pay closes", "bug", "payments-api"),
        ("checkout crash again", "pay crash", "bug", "payments-api"),
    ]
    for title, body, ty, hint in items:
        c.post("/v1/feedback", headers={"X-API-Key": KEY},
               json={"title": title, "body": body, "type": ty, "service_hint": hint})
    return c.post("/v1/clusters/rebuild", headers={"X-API-Key": KEY}).json()["items"]


def test_digest_ranks_feature_demand():
    c = TestClient(app)
    _seed_feedback(c)
    r = c.get("/v1/insights/digest", headers={"X-API-Key": KEY})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["requests"] == 3, items
    assert any("dark mode" in t for t in items[0]["sample_titles"]), items

    p = c.get("/v1/insights/proposals", headers={"X-API-Key": KEY})
    assert p.status_code == 200
    md = p.json()["items"][0]["markdown"]
    assert md.startswith("## Proposal:") and "- " in md


def test_metrics_summary_counts():
    c = TestClient(app)
    _seed_feedback(c)
    r = c.get("/v1/metrics/summary", headers={"X-API-Key": KEY})
    body = r.json()
    assert body["feedback"] == 5 and body["clusters"] == 2, body
    assert body["pr_acceptance"]["rate"] == 0.0
    assert body["signals"] == {}


def test_signals_accept_and_summarize():
    c = TestClient(app)
    r = c.post("/v1/investigations/some-id/feedback", headers={"X-API-Key": KEY},
               json={"signal": "helpful"})
    assert r.status_code == 202, r.text
    c.post("/v1/investigations/some-id/feedback", headers={"X-API-Key": KEY},
           json={"signal": "wrong_cause", "note": "actually the gateway"})
    bad = c.post("/v1/investigations/some-id/feedback", headers={"X-API-Key": KEY},
                 json={"signal": "bogus"})
    assert bad.status_code == 422
    s = c.get("/v1/signals/summary", headers={"X-API-Key": KEY}).json()["signals"]
    assert s == {"helpful": 1, "wrong_cause": 1}, s
    m = c.get("/v1/metrics/summary", headers={"X-API-Key": KEY}).json()
    assert m["signals"]["helpful"] == 1


def test_replay_restores_wiped_index(tmp_path, monkeypatch):
    idx = tmp_path / "idx"
    monkeypatch.setenv("PIL_INDEX_ROOT", str(idx))
    monkeypatch.setenv("PIL_GRAPH_ROOT", str(tmp_path / "g"))
    c = TestClient(app)
    c.post("/v1/repos/sync", headers={"X-API-Key": KEY},
           json={"repo_url": FIX, "alias": "demo"})
    _seed_feedback(c)
    (idx / "00000000-0000-0000-0000-000000000001" / "demo" / "chunks.jsonl").unlink()
    r = c.post("/v1/admin/replay", headers={"X-API-Key": KEY})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reindexed"] and body["reindexed"][0]["chunks"] >= 20, body
    assert body["clusters"] == 2 and body["graph"]["nodes"] > 5
    hits = c.get("/v1/code/search", headers={"X-API-Key": KEY},
                 params={"q": "checkout charge"}).json()["items"]
    assert any("checkout.py" in h["path"] for h in hits)
