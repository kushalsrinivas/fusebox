"""Per-key rate limiting (token bucket) for the public API."""

import time

_buckets: dict[str, list[float]] = {}


def rate_limit(key: str, limit: int = 100, window_s: int = 60) -> bool:
    """Return True if the request is allowed under the rate limit."""
    now = time.time()
    hits = [t for t in _buckets.get(key, []) if now - t < window_s]
    if len(hits) >= limit:
        return False
    hits.append(now)
    _buckets[key] = hits
    return True
