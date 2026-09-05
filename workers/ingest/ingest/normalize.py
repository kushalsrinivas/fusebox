"""Canonical normalization: raw connector payload -> CanonicalFeedbackEvent dict."""

import hashlib
from datetime import datetime, timezone

from .redact import redact

VALID_TYPES = {"bug", "feature_request", "crash", "support", "other"}


def actor_hash(actor: str | None) -> str | None:
    if not actor:
        return None
    return hashlib.sha256(actor.encode()).hexdigest()[:16]


def normalize(raw: dict, tenant_id: str, source: str) -> dict:
    ftype = str(raw.get("type", "other")).lower()
    if ftype not in VALID_TYPES:
        ftype = "other"
    return {
        "tenant_id": tenant_id,
        "source": source,
        "type": ftype,
        "occurred_at": raw.get("occurred_at") or datetime.now(timezone.utc).isoformat(),
        "actor_hash": actor_hash(raw.get("actor")),
        "title": redact(str(raw.get("title", ""))[:300]),
        "body": redact(str(raw.get("body", ""))[:20000]),
        "app_version": raw.get("app_version"),
        "os": raw.get("os"),
        "service_hint": raw.get("service_hint"),
        "external_id": raw.get("external_id"),
        "urls": raw.get("urls", []),
    }
