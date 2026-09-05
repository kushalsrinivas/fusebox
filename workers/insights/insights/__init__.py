"""Feature-request digest: clusters -> ranked proposals (pure, no LLM).

A cluster counts as feature demand when most members are type
feature_request (or its title asks for something and no errors link it).
Ranked by count, tie-broken by recency proxy (member order). The agent
analyst renders these into proposal docs; numbers here stay deterministic.
"""

from __future__ import annotations


def build_digest(clusters: list[dict], feedback_by_id: dict[str, dict],
                 top_n: int = 10) -> list[dict]:
    scored = []
    for c in clusters:
        members = [feedback_by_id.get(mid, {}) for mid in c.get("members", c.get("member_ids", []))]
        members = [m for m in members if m]
        if not members:
            continue
        fr = sum(1 for m in members if m.get("type") == "feature_request")
        ratio = fr / len(members)
        titles = sorted({m.get("title", "") for m in members})
        scored.append({
            "cluster_key": c.get("key"), "title": c.get("title", ""),
            "requests": len(members), "feature_ratio": round(ratio, 2),
            "service_hint": c.get("service_hint"),
            "sample_titles": titles[:3],
            "is_feature_demand": ratio >= 0.5,
        })
    demand = [s for s in scored if s["is_feature_demand"]]
    demand.sort(key=lambda s: s["requests"], reverse=True)
    return demand[:top_n]
