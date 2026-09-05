"""Stripe helpers without the stripe dependency (stdlib + httpx).

- create_checkout_session: hosted checkout for plan upgrades (needs
  STRIPE_SECRET_KEY + a Price per plan; mapping via STRIPE_PRICE_<PLAN>).
- verify_webhook: Stripe-Signature (v1 HMAC-SHA256) check, timestamp-tolerant.
- handle_event: checkout.session.completed -> (tenant_id, plan) to activate.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any


def verify_webhook(raw: bytes, header: str, secret: str,
                   tolerance_s: int = 300, now: float | None = None) -> dict:
    """Verify + parse a Stripe webhook. Raises ValueError on failure."""
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    ts, sigs = parts.get("t"), [v for k, v in
                                (p.split("=", 1) for p in header.split(",") if "=" in p)
                                if k.strip() == "v1"]
    if not ts or not sigs:
        raise ValueError("malformed Stripe-Signature header")
    if abs((now if now is not None else time.time()) - int(ts)) > tolerance_s:
        raise ValueError("webhook timestamp outside tolerance")
    want = hmac.new(secret.encode(), f"{ts}.".encode() + raw,
                    hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(want, s) for s in sigs):
        raise ValueError("webhook signature mismatch")
    return json.loads(raw.decode())


def handle_event(event: dict) -> dict | None:
    """Map checkout.session.completed -> {tenant_id, plan}. None if N/A."""
    if event.get("type") != "checkout.session.completed":
        return None
    obj = event.get("data", {}).get("object", {})
    meta = obj.get("metadata", {}) or {}
    if "tenant_id" in meta and "plan" in meta:
        return {"tenant_id": meta["tenant_id"], "plan": meta["plan"]}
    return None


def create_checkout_session(secret_key: str, price_id: str, tenant_id: str,
                            plan: str, success_url: str, cancel_url: str,
                            _client: Any | None = None) -> dict:
    """Create a Stripe Checkout Session (subscription). _client is the test seam."""
    import httpx

    payload = {
        "mode": "subscription",
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata[tenant_id]": tenant_id,
        "metadata[plan]": plan,
    }
    if _client is not None:
        r = _client.post("https://api.stripe.com/v1/checkout/sessions", data=payload)
    else:
        auth = __import__("base64").b64encode(f"{secret_key}:".encode()).decode()
        with httpx.Client(headers={"Authorization": f"Basic {auth}"},
                          timeout=30) as client:
            r = client.post("https://api.stripe.com/v1/checkout/sessions", data=payload)
    r.raise_for_status()
    data = r.json()
    return {"session_id": data["id"], "url": data["url"]}
