import time

_buckets: dict[str, list[float]] = {}


def check_rate_limit(key: str, limit: int = 100, window_s: int = 60) -> None:
    """In-memory token bucket. Swap for Redis in Phase 6; raises on excess."""
    from fastapi import HTTPException

    now = time.time()
    hits = [t for t in _buckets.get(key, []) if now - t < window_s]
    if len(hits) >= limit:
        raise HTTPException(status_code=429, detail="rate limited")
    hits.append(now)
    _buckets[key] = hits
