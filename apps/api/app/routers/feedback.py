import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field

from .. import quotas
from ..auth import tenant_from_key
from ..db import list_feedback, save_feedback
from ..publish import publish
from ..ratelimit import check_rate_limit

router = APIRouter()


class FeedbackIn(BaseModel):
    source: str = Field(default="api", max_length=32)
    type: str = Field(default="other", max_length=32)
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(default="", max_length=20000)
    app_version: str | None = None
    os: str | None = None
    service_hint: str | None = None
    external_id: str | None = None
    occurred_at: str | None = None


@router.post("/v1/feedback", status_code=202)
def create_feedback(payload: FeedbackIn, tenant_id: str = Depends(tenant_from_key)):
    check_rate_limit(f"fb:{tenant_id}")
    quotas.check("feedback", tenant_id)
    row = save_feedback(tenant_id, payload.model_dump())
    quotas.bump("feedback", tenant_id)
    publish("feedback.raw.v1", row)
    return {"event_id": row["id"], "status": "accepted"}


@router.get("/v1/feedback")
def get_feedback(
    limit: int = Query(default=50, le=200),
    tenant_id: str = Depends(tenant_from_key),
):
    return {"items": list_feedback(tenant_id, limit)}


@router.post("/v1/feedback/csv", status_code=202)
async def import_csv(
    file: UploadFile = File(...), tenant_id: str = Depends(tenant_from_key)
):
    raw = (await file.read()).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    rows = [line for line in reader if (line.get("title") or "").strip()]
    quotas.check("feedback", tenant_id)
    accepted = 0
    for line in rows:
        row = save_feedback(
            tenant_id,
            {
                "source": "csv",
                "type": (line.get("type") or "other").strip() or "other",
                "title": (line.get("title") or "").strip()[:300],
                "body": (line.get("body") or "")[:20000],
                "app_version": (line.get("app_version") or None),
                "occurred_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        publish("feedback.raw.v1", row)
        accepted += 1
    quotas.bump("feedback", tenant_id, accepted)
    return {"accepted": accepted}
