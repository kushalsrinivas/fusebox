import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.config as config
from app.db import clear_memory
from app.main import app

KEY = "dev-key"
FIX = str(Path(__file__).parent.parent.parent.parent
          / "workers" / "indexer" / "tests" / "fixtures" / "demo-repo")


@pytest.fixture()
def idx_root(tmp_path, monkeypatch):
    monkeypatch.setenv("PIL_INDEX_ROOT", str(tmp_path / "idx"))
    return str(tmp_path / "idx")


def setup_function(_):
    clear_memory()
    config.API_KEYS.setdefault(KEY, "00000000-0000-0000-0000-000000000001")
    # isolate on-disk default index from test envs that don't monkeypatch
    os.environ.pop("PIL_INDEX_ROOT", None)


def test_sync_and_search_grounded(idx_root):
    os.environ["PIL_INDEX_ROOT"] = idx_root
    c = TestClient(app)
    r = c.post("/v1/repos/sync", headers={"X-API-Key": KEY},
               json={"repo_url": FIX, "alias": "demo"})
    assert r.status_code == 200, r.text
    assert r.json()["chunks"] >= 20

    r2 = c.get("/v1/repos", headers={"X-API-Key": KEY})
    assert [i["repo"] for i in r2.json()["items"]] == ["demo"]

    r3 = c.get("/v1/code/search", headers={"X-API-Key": KEY},
               params={"q": "capture payment timeout", "top_k": 3})
    assert r3.status_code == 200
    paths = [h["path"] for h in r3.json()["items"]]
    assert any("checkout.py" in p for p in paths), paths


def test_github_push_webhook_reindexes(idx_root):
    os.environ["PIL_INDEX_ROOT"] = idx_root
    c = TestClient(app)
    r = c.post("/v1/webhooks/github", headers={"X-API-Key": KEY, "X-GitHub-Event": "push"},
               json={"repository": {"clone_url": FIX}, "head_commit": {"id": "abc"}})
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "reindexed"

    r2 = c.post("/v1/webhooks/github", headers={"X-API-Key": KEY, "X-GitHub-Event": "ping"},
                json={"zen": "hi"})
    assert r2.json()["status"] == "ok"
