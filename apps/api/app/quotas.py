"""Quota gate: call check() before metered work, bump() after it succeeds."""

from fastapi import HTTPException

from . import db


def check(kind: str, tenant_id: str) -> dict:
    try:
        from billing import quota_check, upgrade_hint
    except ImportError:
        return {"allowed": True}
    plan = db.get_plan(tenant_id)
    used = db.usage_used(tenant_id, kind)
    q = quota_check(plan, kind, used)
    if not q["allowed"]:
        raise HTTPException(status_code=429, detail={
            "error": upgrade_hint(plan, kind), "kind": kind,
            "limit": q["limit"], "used": used, "plan": plan})
    return {**q, "used": used, "plan": plan}


def bump(kind: str, tenant_id: str, n: int = 1) -> int:
    return db.usage_bump(tenant_id, kind, n)
