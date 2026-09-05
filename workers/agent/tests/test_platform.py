"""Platform client tests: tools read live API data via injected test client."""

import os
import sys

from fastapi.testclient import TestClient

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, os.path.join(ROOT, "apps", "api"))

from app import db as api_db  # noqa: E402
from app.main import app as api_app  # noqa: E402

from agent import platform as pf  # noqa: E402
from agent.tools import deploys_list, errors_recent  # noqa: E402

TENANT = "00000000-0000-0000-0000-000000000001"


def _seed():
    api_db.clear_memory()
    api_db.save_deployment(TENANT, {"service": "payments-api", "version": "1.4.3",
                                    "commit_sha": "ab12",
                                    "deployed_at": "2026-09-05T10:00:00Z"})
    api_db.record_error(TENANT, {"fingerprint": "fp1", "service": "payments-api",
                                 "title": "capture failed: timeout"})


def _live_client():
    _seed()
    return TestClient(api_app, headers={"X-API-Key": "dev-key"})


def test_platform_reads_live_deploys_and_groups():
    client = _live_client()
    deploys = pf.get_deploys("payments-api", _client=client)
    assert deploys and deploys[0]["commit_sha"] == "ab12", deploys
    groups = pf.get_error_groups("payments-api", _client=client)
    assert groups and groups[0]["fingerprint"] == "fp1", groups
    corr = pf.get_correlation("payments-api", "2026-09-05T12:00:00Z",
                              _client=client)
    assert corr and corr["suspects"][0]["deployment"]["commit_sha"] == "ab12"


def test_tools_use_live_backend(monkeypatch):
    client = _live_client()
    orig_deploys = pf.get_deploys
    orig_groups = pf.get_error_groups
    monkeypatch.setattr(pf, "get_deploys",
                        lambda service, _client=None: orig_deploys(service, _client=client))
    monkeypatch.setattr(pf, "get_error_groups",
                        lambda service, _client=None: orig_groups(service, _client=client))
    d = deploys_list.invoke({"service": "payments-api", "tenant_id": TENANT})
    assert d[0]["commit_sha"] == "ab12", d
    e = errors_recent.invoke({"service": "payments-api", "tenant_id": TENANT})
    assert e[0]["fingerprint"] == "fp1", e


def test_platform_returns_none_without_config(monkeypatch):
    monkeypatch.delenv("PIL_API_URL", raising=False)
    monkeypatch.delenv("PIL_API_KEY", raising=False)
    assert pf.get_deploys("svc") is None
    assert pf.get_error_groups("svc") is None
