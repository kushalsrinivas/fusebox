"""Regression-risk score (pure function).

Inputs: touched paths, reference counts {path: #chunks importing it},
sensitive-path hits, diff size. Output: score 0-1 + level + factors +
blast_radius. Thresholds: <0.35 low, <0.65 medium, else high.
"""

from __future__ import annotations

SENSITIVE = ("migrations/", "infra/", "auth/", "payments/")


def score_risk(paths: list[str], refcounts: dict[str, int] | None = None,
               sensitive: tuple[str, ...] = SENSITIVE,
               diff_lines: int = 0) -> dict:
    refcounts = refcounts or {}
    factors: list[str] = []
    score = 0.0

    fanout = sum(refcounts.get(p, 0) for p in paths)
    if fanout >= 10:
        score += 0.35
        factors.append(f"high fan-out: {fanout} referencing chunks")
    elif fanout >= 3:
        score += 0.2
        factors.append(f"moderate fan-out: {fanout} referencing chunks")

    sens = [p for p in paths if any(s in p for s in sensitive)]
    if sens:
        score += 0.3
        factors.append(f"sensitive area: {', '.join(sens)}")

    if diff_lines > 200:
        score += 0.2
        factors.append(f"large diff: {diff_lines} lines")
    elif diff_lines > 50:
        score += 0.1
        factors.append(f"medium diff: {diff_lines} lines")

    if len(paths) >= 5:
        score += 0.1
        factors.append(f"wide diff: {len(paths)} files")

    score = round(min(score, 1.0), 2)
    level = "low" if score < 0.35 else ("medium" if score < 0.65 else "high")
    return {"score": score, "level": level, "factors": factors,
            "blast_radius": sorted(paths),
            "requires_two_approvals": level == "high"}
