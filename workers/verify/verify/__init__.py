"""Post-deploy verification verdicts (pure functions).

Compares error occurrences before vs after a fix's approval time:
- verified_fixed: errors stopped (0) or dropped >=90%
- regressed:      errors grew >20% after the fix
- inconclusive:   window too early, no baseline, or ambiguous middle

A scheduler calls this every N hours in prod; the API exposes it on demand.
"""

from __future__ import annotations

FIX_THRESHOLD = 0.9
REGRESS_THRESHOLD = 0.2


def verify_fix(before: int, after: int, elapsed_h: float,
               min_window_h: float = 24.0) -> dict:
    if elapsed_h < min_window_h:
        return {"verdict": "inconclusive",
                "reason": f"only {elapsed_h:.1f}h elapsed; need {min_window_h}h",
                "delta": None}
    if before <= 0:
        return {"verdict": "inconclusive", "reason": "no pre-fix baseline",
                "delta": None}
    delta = round((after - before) / before, 3)
    if after == 0 or delta <= -FIX_THRESHOLD:
        return {"verdict": "verified_fixed",
                "reason": f"errors dropped {delta:.0%} vs baseline", "delta": delta}
    if delta > REGRESS_THRESHOLD:
        return {"verdict": "regressed",
                "reason": f"errors grew {delta:.0%} vs baseline", "delta": delta}
    return {"verdict": "inconclusive",
            "reason": f"ambiguous middle ({delta:.0%}); keep watching",
            "delta": delta}


def overall(results: list[dict]) -> dict:
    """Roll up per-group verdicts: regressed wins, then fixed, else waiting."""
    verdicts = [r["verdict"] for r in results]
    if any(v == "regressed" for v in verdicts):
        status = "regressed"
    elif results and all(v == "verified_fixed" for v in verdicts):
        status = "verified_fixed"
    else:
        status = "inconclusive"
    return {"status": status, "groups": results}
