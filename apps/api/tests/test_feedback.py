from fastapi.testclient import TestClient

from app.db import clear_memory
from app.main import app

KEY = "dev-key"
OTHER_KEY = "other-key"

import app.config as config


def setup_function(_):
    clear_memory()
    # second tenant for isolation test
    config.API_KEYS[OTHER_KEY] = "00000000-0000-0000-0000-000000000002"


def client():
    return TestClient(app)


def test_post_then_list():
    c = client()
    r = c.post(
        "/v1/feedback",
        headers={"X-API-Key": KEY},
        json={"title": "checkout crash on pay", "body": "taps pay, app closes"},
    )
    assert r.status_code == 202, r.text
    r2 = c.get("/v1/feedback", headers={"X-API-Key": KEY})
    assert r2.status_code == 200
    assert any(i["title"] == "checkout crash on pay" for i in r2.json()["items"])


def test_tenant_isolation():
    c = client()
    c.post("/v1/feedback", headers={"X-API-Key": KEY}, json={"title": "tenant-a-only"})
    r = c.get("/v1/feedback", headers={"X-API-Key": OTHER_KEY})
    assert r.status_code == 200
    assert all(i["title"] != "tenant-a-only" for i in r.json()["items"])


def test_auth_required():
    c = client()
    assert c.get("/v1/feedback").status_code in (401, 422)
    assert c.post("/v1/feedback", json={"title": "x"}).status_code in (401, 422)


def test_csv_import():
    c = client()
    csv_body = "title,body,type\nlogin fails,500 on login,bug\nslow feed,timeline lags,other\n"
    r = c.post(
        "/v1/feedback/csv",
        headers={"X-API-Key": KEY},
        files={"file": ("in.csv", csv_body, "text/csv")},
    )
    assert r.status_code == 202, r.text
    assert r.json()["accepted"] == 2
