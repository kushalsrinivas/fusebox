"""Observability ingest: Sentry webhook, error batch import, deployments, correlate.

Sentry wiring: create an issue-alert webhook pointing at
`POST /v1/webhooks/sentry` with `X-API-Key: <tenant key>`.
Backfill: POST historical export to `/v1/telemetry/errors/batch`.
"""

import hashlib

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from .. import quotas
from ..auth import tenant_from_key
from ..db import list_deployments, list_error_groups, record_error, save_deployment
from ..ratelimit import check_rate_limit

router = APIRouter()


def _lib():
    try:
        from correlation import find_suspects
        return find_suspects
    except ImportError:
        return None


def _fingerprint(title: str, culprit: str) -> str:
    return hashlib.sha256(f"{title}\n{culprit}".encode()).hexdigest()[:16]


def _normalize_sentry(payload: dict) -> dict:
    """Defensively map Sentry issue-alert payloads to a canonical error."""
    event = payload.get("event") or {}
    title = str(payload.get("title") or event.get("title")
                or payload.get("message") or "unknown error")[:300]
    culprit = str(event.get("culprit") or payload.get("culprit") or "")[:300]
    contexts = event.get("contexts") or {}
    release = (event.get("release")
               or (contexts.get("release") or {}).get("version"))
    project = str(payload.get("project_slug") or payload.get("project")
                  or event.get("project") or "unknown")
    return {
        "fingerprint": str(payload.get("fingerprint") or event.get("fingerprint")
                           or _fingerprint(title, culprit)),
        "service": project,
        "release": str(release)[:64] if release else None,
        "title": title,
        "level": str(event.get("level") or "error"),
        "message": str(event.get("message") or title)[:2000],
        "event_id": event.get("event_id"),
        "ts": event.get("datetime") or event.get("timestamp"),
    }


@router.post("/v1/webhooks/sentry", status_code=202)
def sentry_webhook(payload: dict, tenant_id: str = Depends(tenant_from_key)):
    check_rate_limit(f"sentry:{tenant_id}", limit=500)
    quotas.check("feedback", tenant_id)
    group = record_error(tenant_id, _normalize_sentry(payload))
    quotas.bump("feedback", tenant_id)
    return {"group_id": group["id"], "fingerprint": group["fingerprint"],
            "count": group["count"], "status": "accepted"}


class ErrorBatchIn(BaseModel):
    items: list[dict] = Field(max_length=500)


@router.post("/v1/telemetry/errors/batch", status_code=202)
def errors_batch(payload: ErrorBatchIn, tenant_id: str = Depends(tenant_from_key)):
    quotas.check("feedback", tenant_id)
    accepted = 0
    for item in payload.items:
        record_error(tenant_id, _normalize_sentry(item))
        accepted += 1
    quotas.bump("feedback", tenant_id, accepted)
    return {"accepted": accepted}


@router.get("/v1/errors/groups")
def error_groups(service: str | None = Query(default=None),
                 limit: int = Query(default=50, le=200),
                 tenant_id: str = Depends(tenant_from_key)):
    return {"items": list_error_groups(tenant_id, service, limit)}


class DeployIn(BaseModel):
    service: str = Field(min_length=1, max_length=100)
    version: str = Field(default="", max_length=64)
    commit_sha: str | None = Field(default=None, max_length=64)
    env: str = Field(default="production", max_length=32)
    deployed_at: str | None = None


@router.post("/v1/deploys", status_code=202)
def create_deploy(payload: DeployIn, tenant_id: str = Depends(tenant_from_key)):
    row = save_deployment(tenant_id, payload.model_dump())
    return {"id": row["id"], "status": "accepted"}


@router.get("/v1/deploys")
def get_deploys(service: str | None = Query(default=None),
                limit: int = Query(default=50, le=200),
                tenant_id: str = Depends(tenant_from_key)):
    return {"items": list_deployments(tenant_id, service, limit)}


@router.get("/v1/correlate")
def correlate(service: str = Query(min_length=1),
              spike_start: str = Query(min_length=1),
              window_h: int = Query(default=6, le=72),
              tenant_id: str = Depends(tenant_from_key)):
    find_suspects = _lib()
    deploys = list_deployments(tenant_id, service, limit=200)
    if find_suspects is None:
        return {"service": service, "spike_start": spike_start,
                "suspects": [], "note": "correlation lib not installed"}
    try:
        suspects = find_suspects(deploys, spike_start, service, window_h)
    except (ValueError, KeyError) as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"bad spike_start: {e}")
    return {"service": service, "spike_start": spike_start,
            "window_h": window_h, "suspects": suspects}
