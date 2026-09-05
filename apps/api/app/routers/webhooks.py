from fastapi import APIRouter, Depends, Request

from ..auth import tenant_from_key
from ..db import save_feedback
from ..publish import publish

router = APIRouter()

ALLOWED = {"zendesk", "intercom", "appstore", "slack", "sentry"}


@router.post("/v1/webhooks/{source}", status_code=202)
async def webhook(source: str, req: Request, tenant_id: str = Depends(tenant_from_key)):
    if source not in ALLOWED:
        return {"status": "ignored", "reason": f"unknown source {source}"}
    try:
        payload = await req.json()
    except Exception:
        payload = {}
    title = str(payload.get("title") or payload.get("subject") or f"{source} event")[:300]
    body = str(payload.get("body") or payload.get("description") or "")[:20000]
    row = save_feedback(
        tenant_id,
        {"source": source, "type": "support", "title": title, "body": body},
    )
    publish("feedback.raw.v1", row)
    return {"event_id": row["id"], "status": "accepted"}
