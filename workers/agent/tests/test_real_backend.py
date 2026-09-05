import os

import pytest

pil_indexer = pytest.importorskip("pil_indexer")

from agent.tools import code_read, code_search  # noqa: E402
from pil_indexer.sync import sync_repo  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "..", "..", "indexer",
                   "tests", "fixtures", "demo-repo")
TENANT = "00000000-0000-0000-0000-000000000001"


@pytest.fixture()
def real_index(tmp_path, monkeypatch):
    root = str(tmp_path / "idx")
    sync_repo(root, TENANT, FIX, alias="demo")
    monkeypatch.setenv("PIL_INDEX_ROOT", root)
    return root


def test_code_search_hits_real_index(real_index):
    hits = code_search.invoke({"query": "capture payment timeout",
                               "tenant_id": TENANT})
    assert hits, "expected real index hits"
    assert any("checkout.py" in h["path"] for h in hits), hits
    assert all(h["ref"].startswith("index://demo/") for h in hits)


def test_code_read_from_real_index(real_index):
    out = code_read.invoke({"path": "apps/payments/checkout.py",
                            "tenant_id": TENANT, "start": 1, "end": 12})
    assert out["ref"].startswith("index://demo/")
    assert "charge" in out["content"] or "checkout" in out["content"]


def test_falls_back_to_stub_without_index(monkeypatch):
    monkeypatch.delenv("PIL_INDEX_ROOT", raising=False)
    hits = code_search.invoke({"query": "anything", "tenant_id": TENANT})
    assert hits and hits[0]["ref"].startswith("github://")
