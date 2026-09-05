from fastapi.testclient import TestClient

import app.config as config
from app.db import clear_memory
from app.main import app

KEY = "dev-key"


def setup_function(_):
    clear_memory()
    config.API_KEYS.setdefault(KEY, "00000000-0000-0000-0000-000000000001")


def test_onboarding_checklist_flips_as_you_go():
    c = TestClient(app)
    s0 = c.get("/v1/onboarding/status", headers={"X-API-Key": KEY}).json()
    assert s0["complete"] is False
    assert all(s["done"] is False for s in s0["steps"])

    r = c.post("/v1/onboarding/demo", headers={"X-API-Key": KEY})
    assert r.status_code == 200, r.text
    assert r.json()["feedback"] == 5 and r.json()["clusters"] >= 2

    s1 = c.get("/v1/onboarding/status", headers={"X-API-Key": KEY}).json()
    by_key = {s["key"]: s["done"] for s in s1["steps"]}
    assert by_key == {"feedback": True, "repos": True, "clusters": True, "actions": False}
