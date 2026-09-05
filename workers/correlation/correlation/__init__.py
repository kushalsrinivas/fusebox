"""Deploy-proximity correlation (pure functions over row dicts).

No I/O, no deps: the API layer supplies tenant-scoped rows, this module
ranks suspects. Deterministic and fully unit-testable.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt


def find_suspects(deploys: list[dict], spike_start: str, service: str,
                  window_h: int = 6) -> list[dict]:
    """Rank deploys of `service` inside [spike-window, spike] by recency.

    Score 0-1: 1.0 = deployed at spike start, decaying linearly to 0 at the
    window edge. Deploys after the spike are excluded (can't cause the past).
    """
    spike = _parse(spike_start)
    window = timedelta(hours=window_h)
    out = []
    for d in deploys:
        if d.get("service") != service:
            continue
        try:
            dep = _parse(str(d["deployed_at"]))
        except (KeyError, ValueError):
            continue
        delta = (spike - dep).total_seconds()
        if delta < 0 or delta > window.total_seconds():
            continue
        score = round(1.0 - delta / window.total_seconds(), 3)
        mins = int(delta // 60)
        out.append({
            "deployment": {k: d.get(k) for k in
                           ("id", "service", "version", "commit_sha", "env", "deployed_at")},
            "score": score,
            "reason": f"deployed {mins}m before spike (window {window_h}h)",
        })
    out.sort(key=lambda s: s["score"], reverse=True)
    return out


def detect_spike(hourly_counts: list[int], z: float = 3.0,
                 min_baseline: int = 5) -> int | None:
    """Z-score spike index vs all prior buckets. None when no baseline.

    Returns the FIRST index whose count exceeds mean + z*std of history.
    """
    for i in range(1, len(hourly_counts)):
        hist = hourly_counts[:i]
        mean = sum(hist) / len(hist)
        if mean < min_baseline:
            continue
        var = sum((c - mean) ** 2 for c in hist) / len(hist)
        std = math.sqrt(var) or 1.0
        if hourly_counts[i] > mean + z * std:
            return i
    return None
