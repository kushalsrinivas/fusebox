"""Phase 0 clustering stub: normalized token Jaccard. Phase 3 replaces with embeddings."""

import re

_WORD = re.compile(r"[a-z0-9]+")


def tokens(s: str) -> set[str]:
    return set(_WORD.findall(s.lower()))


def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def should_merge(a_title: str, b_title: str) -> str:
    """Returns 'auto' | 'review' | 'new' per arch thresholds (mapped to Jaccard)."""
    s = similarity(a_title, b_title)
    if s >= 0.55:
        return "auto"
    if s >= 0.35:
        return "review"
    return "new"
