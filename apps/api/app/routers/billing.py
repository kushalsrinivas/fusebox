"""Billing: plan status, Stripe checkout, Stripe webhook."""

import os

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from .. import db
from ..auth import tenant_from_key

router = APIRouter()


@router.get("/v1/billing/status")
def billing_status(tenant_id: str = Depends(tenant_from_key)):
    try:
        from billing import PLANS, quota_check
    except ImportError:
        raise HTTPException(status_code=501, detail="billing lib not installed")
    plan = db.get_plan(tenant_id)
    usage = {k: db.usage_used(tenant_id, k)
             for k in ("feedback", "investigations", "actions")}
    return {"plan": plan, "plans": PLANS,
            "usage": usage,
            "quotas": {k: quota_check(plan, k, v) for k, v in usage.items()}}


@router.get("/v1/audit")
def get_audit(limit: int = 50, tenant_id: str = Depends(tenant_from_key)):
    return {"items": db.list_audit(tenant_id, limit)}


class CheckoutIn(BaseModel):
    plan: str = Field(pattern="^(pro|enterprise)$")
    success_url: str = Field(default="http://localhost:3000/billing/success")
    cancel_url: str = Field(default="http://localhost:3000/billing/cancel")


@router.post("/v1/billing/checkout")
def checkout(payload: CheckoutIn, tenant_id: str = Depends(tenant_from_key)):
    secret = os.getenv("STRIPE_SECRET_KEY", "")
    price = os.getenv(f"STRIPE_PRICE_{payload.plan.upper()}", "")
    if not secret or not price:
        raise HTTPException(status_code=501, detail={
            "error": "billing not configured",
            "setup": "set STRIPE_SECRET_KEY + STRIPE_PRICE_PRO/ENTERPRISE; "
                     "see docs/CONNECTORS.md#billing. Dev alternative: "
                     "POST /v1/admin/plan with PIL_ADMIN_KEY."})
    from billing.stripe import create_checkout_session
    try:
        out = create_checkout_session(secret, price, tenant_id, payload.plan,
                                      payload.success_url, payload.cancel_url)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"stripe error: {e}")
    db.log_audit(tenant_id, tenant_id, "checkout_started",
                 {"plan": payload.plan, "session_id": out["session_id"]})
    return out


@router.post("/v1/webhooks/stripe")
async def stripe_webhook(req: Request,
                         stripe_signature: str | None = Header(default=None)):
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=501, detail="billing not configured")
    if not stripe_signature:
        raise HTTPException(status_code=401, detail="missing signature")
    from billing.stripe import handle_event, verify_webhook
    try:
        event = verify_webhook(await req.body(), stripe_signature, secret)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    routed = handle_event(event)
    if routed:
        db.set_plan(routed["tenant_id"], routed["plan"])
        db.log_audit(routed["tenant_id"], "stripe", "plan_activated",
                     {"plan": routed["plan"]})
        return {"status": "plan_activated", **routed}
    return {"status": "ignored"}
