"""Feedback grouping: near-duplicate reports -> IssueCluster candidates.

Similarity = max(token Jaccard, embedding cosine when pil_indexer is
importable). Union-find merging with per-tenant tunable thresholds.
Pure functions over feedback row dicts (id/title/body/service_hint).
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+")

AUTO_MERGE = 0.55
REVIEW_MERGE = 0.35


def tokens(s: str) -> set[str]:
    return set(_WORD.findall((s or "").lower()))


def _embedder():
    try:
        from pil_indexer.embed import HashEmbedder, cosine  # type: ignore
        return HashEmbedder(), cosine
    except ImportError:
        return None, None


def similarity(a_title: str, a_body: str, b_title: str, b_body: str) -> float:
    ta, tb = tokens(f"{a_title} {a_body[:500]}"), tokens(f"{b_title} {b_body[:500]}")
    jac = len(ta & tb) / (len(ta | tb) or 1)
    emb, cos = _embedder()
    if emb is None:
        return jac
    c = cos(emb.embed(f"{a_title} {a_body[:500]}"),
            emb.embed(f"{b_title} {b_body[:500]}"))
    return max(jac, c)


def group_feedback(items: list[dict], auto: float = AUTO_MERGE,
                   review: float = REVIEW_MERGE) -> list[dict]:
    """Union-find over pairwise similarity. Returns cluster dicts.

    Each cluster: {key, title (longest member title), members:[ids],
    count, service_hint (majority), status: auto|review}.
    Pairwise is O(n^2) — fine for Phase 3 volumes; LSH/blocking later.
    """
    parent = list(range(len(items)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    edge_kind: dict[tuple[int, int], str] = {}
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            s = similarity(items[i].get("title", ""), items[i].get("body", ""),
                           items[j].get("title", ""), items[j].get("body", ""))
            if s >= auto:
                union(i, j)
                edge_kind[(i, j)] = "auto"
            elif s >= review:
                edge_kind[(i, j)] = "review"

    groups: dict[int, list[int]] = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(i)

    clusters = []
    for members in groups.values():
        rows = [items[i] for i in members]
        title = max((r.get("title", "") for r in rows), key=len, default="")
        hints = [r.get("service_hint") for r in rows if r.get("service_hint")]
        hint = max(set(hints), key=hints.count) if hints else None
        weak = any(edge_kind.get((min(a, b), max(a, b))) == "review"
                   for x, a in enumerate(members) for b in members[x + 1:])
        clusters.append({
            "key": f"c_{min(members)}",
            "title": title,
            "members": [r["id"] for r in rows],
            "count": len(rows),
            "service_hint": hint,
            "status": "review" if (weak and len(rows) > 1) else "auto",
        })
    clusters.sort(key=lambda c: c["count"], reverse=True)
    return clusters
