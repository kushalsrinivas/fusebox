"""Post-deploy verification: error deltas around an action's approval time."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import db
from ..auth import tenant_from_key

router = APIRouter()


def _hours_between(a: str, b: str) -> float:
    ta = datetime.fromisoformat(a.replace("Z", "+00:00"))
    tb = datetime.fromisoformat(b.replace("Z", "+00:00"))
    return (tb - ta).total_seconds() / 3600


def _linked_fingerprints(action: dict, result: dict) -> list[str]:
    fps: list[str] = []
    for h in result.get("hypotheses", []):
        for c in h.get("citations", []):
            if c.startswith("pil://errors/"):
                fp = c.split("/", 3)[-1]
                if fp not in fps:
                    fps.append(fp)
    return fps


@router.post("/v1/actions/{aid}/verify")
def verify_action(aid: str, window_h: float = Query(default=24.0, le=24 * 30),
                  tenant_id: str = Depends(tenant_from_key)):
    try:
        from verify import overall, verify_fix
    except ImportError:
        raise HTTPException(status_code=501, detail="verify lib not installed")
    action = db.get_action(tenant_id, aid)
    if action is None:
        raise HTTPException(status_code=404, detail="action not found")
    if action["status"] not in ("approved", "validated"):
        raise HTTPException(status_code=422, detail={
            "error": f"nothing deployed yet (action is {action['status']})",
            "hint": "verify runs after approve/merge; earlier is always inconclusive"})

    inv = db.latest_investigation(tenant_id, action["cluster_id"]) \
        if action.get("cluster_id") else None
    result = (inv or {}).get("result", {}) if isinstance(inv, dict) else {}
    fps = _linked_fingerprints(action, result)
    if not fps and (action.get("cluster_id") or ""):
        cluster = db.get_cluster(tenant_id, action["cluster_id"])
        svc = (cluster or {}).get("service_hint")
        fps = [g["fingerprint"] for g in db.list_error_groups(tenant_id, svc)] if svc else []

    from datetime import timedelta
    approved = action["created_at"]
    now = datetime.now(timezone.utc).isoformat()
    elapsed = _hours_between(approved, now)
    start = (datetime.fromisoformat(approved.replace("Z", "+00:00"))
             - timedelta(hours=window_h)).isoformat()
    end = (datetime.fromisoformat(approved.replace("Z", "+00:00"))
           + timedelta(hours=window_h)).isoformat()

    groups = []
    for fp in fps:
        before = db.count_occurrences(tenant_id, fp, since=start, until=approved)
        after = db.count_occurrences(tenant_id, fp, since=approved, until=end)
        v = verify_fix(before, after, elapsed, min_window_h=min(window_h, 24.0))
        groups.append({"fingerprint": fp, "before": before, "after": after, **v})
    rolled = overall(groups)
    row = db.save_verification(tenant_id, aid, rolled["status"], rolled)
    return {"verification_id": row["id"], **rolled, "elapsed_h": round(elapsed, 2)}


@router.get("/v1/verifications")
def get_verifications(action_id: str | None = None,
                      tenant_id: str = Depends(tenant_from_key)):
    return {"items": db.list_verifications(tenant_id, action_id)}
