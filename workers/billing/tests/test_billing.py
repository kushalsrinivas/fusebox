import hashlib
import hmac
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from billing import PLANS, quota_check, upgrade_hint  # noqa: E402
from billing.stripe import (create_checkout_session, handle_event,  # noqa: E402
                            verify_webhook)


def test_free_quotas_block_at_limit():
    assert quota_check("free", "feedback", 499)["allowed"] is True
    q = quota_check("free", "feedback", 500)
    assert q["allowed"] is False and q["remaining"] == 0 and q["limit"] == 500
    assert "pro" in upgrade_hint("free", "feedback").lower()


def test_pro_and_enterprise_allow_more():
    assert quota_check("pro", "investigations", 4999)["allowed"] is True
    assert quota_check("enterprise", "actions", 10**6)["allowed"] is True
    assert quota_check("free", "unknown_kind", 10**9)["allowed"] is True
    assert set(PLANS) == {"free", "pro", "enterprise"}


def _sign(secret, payload, ts):
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def test_stripe_webhook_verify_and_route():
    secret = "whsec_test"
    event = {"type": "checkout.session.completed",
             "data": {"object": {"metadata": {"tenant_id": "t1", "plan": "pro"}}}}
    raw = json.dumps(event).encode()
    ts = str(int(time.time()))
    parsed = verify_webhook(raw, _sign(secret, raw, ts), secret)
    assert handle_event(parsed) == {"tenant_id": "t1", "plan": "pro"}


def test_stripe_webhook_rejects_bad_sig_and_stale():
    secret = "whsec_test"
    raw = b'{"type":"x"}'
    ts = str(int(time.time()))
    try:
        verify_webhook(raw, f"t={ts},v1=deadbeef", secret)
        raise AssertionError("should have raised")
    except ValueError:
        pass
    old = str(int(time.time()) - 10_000)
    try:
        verify_webhook(raw, _sign(secret, raw, old), secret)
        raise AssertionError("should have raised")
    except ValueError:
        pass
    assert handle_event({"type": "invoice.paid"}) is None


class FakeResp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"id": "cs_123", "url": "https://checkout.stripe.com/cs_123"}


class FakeClient:
    def __init__(self):
        self.posts = []

    def post(self, url, data=None):
        self.posts.append((url, data))
        return FakeResp()


def test_checkout_session_posts_price_and_metadata():
    c = FakeClient()
    out = create_checkout_session("sk_test", "price_1", "t1", "pro",
                                  "https://x/s", "https://x/c", _client=c)
    assert out["session_id"] == "cs_123" and out["url"].startswith("https://")
    url, data = c.posts[0]
    assert "stripe.com" in url and data["metadata[plan]"] == "pro"
