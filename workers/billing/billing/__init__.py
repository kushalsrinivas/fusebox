"""Plans and quotas (pure). Usage kinds: feedback, investigations, actions.

Free is generous enough for a pilot; over-quota calls get 429 + upgrade
hint (never silent drops). Monthly reset is a scheduler job in prod;
counters here are per-period and reset via reset_counters().
"""

from __future__ import annotations

PLANS = {
    "free": {"feedback": 500, "investigations": 50, "actions": 20,
             "label": "Free pilot"},
    "pro": {"feedback": 50_000, "investigations": 5_000, "actions": 1_000,
            "label": "Pro"},
    "enterprise": {"feedback": 10**9, "investigations": 10**9,
                   "actions": 10**9, "label": "Enterprise"},
}


def quota_check(plan: str, kind: str, used: int) -> dict:
    """Return {allowed, remaining, limit}. Unknown kinds are never blocked."""
    limit = PLANS.get(plan, PLANS["free"]).get(kind)
    if limit is None:
        return {"allowed": True, "remaining": None, "limit": None}
    return {"allowed": used < limit, "remaining": max(limit - used, 0),
            "limit": limit}


def upgrade_hint(plan: str, kind: str) -> str:
    nxt = "pro" if plan == "free" else "enterprise"
    return (f"Quota exceeded for {kind} on the {plan} plan. "
            f"Upgrade to {nxt} (POST /v1/billing/checkout) or contact sales.")
