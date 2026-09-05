"""Onboarding: checklist status + one-click demo dataset.

Try-without-connecting: POST /v1/onboarding/demo seeds synthetic feedback,
a deploy, and error groups, then rebuilds clusters — first investigation in
under a minute, no GitHub/Sentry required.
"""

from fastapi import APIRouter, Depends

from .. import db
from ..auth import tenant_from_key

router = APIRouter()

DEMO_FEEDBACK = [
    ("checkout crash when tapping pay", "tap pay, app closes on ios", "bug", "payments-api"),
    ("checkout crash on tap pay button", "closes every time on pay", "bug", "payments-api"),
    ("capture timeout on pay", "pay screen hangs then dies", "bug", "payments-api"),
    ("dark mode please", "oled night display for reading", "feature_request", None),
    ("oled dark theme", "night reading mode", "feature_request", None),
]


@router.get("/v1/onboarding/status")
def onboarding_status(tenant_id: str = Depends(tenant_from_key)):
    has_feedback = len(db.list_feedback(tenant_id, 1)) > 0
    has_clusters = len(db.list_clusters(tenant_id)) > 0
    has_deploys = len(db.list_deployments(tenant_id, None, 1)) > 0
    has_errors = len(db.list_error_groups(tenant_id, None, 1)) > 0
    has_actions = len(db.list_actions(tenant_id)) > 0
    steps = [
        {"key": "feedback", "label": "Ingest feedback (API, CSV, or demo data)", "done": has_feedback},
        {"key": "repos", "label": "Sync a repo (or use demo signals)", "done": has_deploys or has_errors},
        {"key": "clusters", "label": "Rebuild clusters", "done": has_clusters},
        {"key": "actions", "label": "Propose + approve a fix", "done": has_actions},
    ]
    return {"steps": steps, "complete": all(s["done"] for s in steps),
            "plan": db.get_plan(tenant_id)}


@router.post("/v1/onboarding/demo")
def onboarding_demo(tenant_id: str = Depends(tenant_from_key)):
    from .. import quotas

    quotas.check("feedback", tenant_id)
    n = 0
    for title, body, ty, hint in DEMO_FEEDBACK:
        db.save_feedback(tenant_id, {"source": "demo", "type": ty, "title": title,
                                     "body": body, "service_hint": hint})
        n += 1
    quotas.bump("feedback", tenant_id, n)
    db.save_deployment(tenant_id, {"service": "payments-api", "version": "1.4.3",
                                   "commit_sha": "ab12",
                                   "deployed_at": "2026-09-05T10:00:00Z"})
    db.record_error(tenant_id, {"fingerprint": "demo-capture-timeout",
                                "service": "payments-api",
                                "title": "capture failed: timeout",
                                "ts": "2026-09-05T12:00:00Z"})
    try:
        from ingest.grouping import group_feedback
        rows = db.list_feedback(tenant_id, 1000)
        items = [{"id": r["id"], "title": r["title"], "body": r.get("body", ""),
                  "service_hint": r.get("service_hint")} for r in rows]
        clusters = db.replace_clusters(tenant_id, group_feedback(items))
    except ImportError:
        clusters = []
    db.log_audit(tenant_id, tenant_id, "demo_seeded", {"feedback": n})
    return {"feedback": n, "clusters": len(clusters),
            "next": "POST /v1/clusters/{id}/investigate on the payments-api cluster"}
