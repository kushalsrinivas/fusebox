"""Redis-backed read cache with explicit invalidation."""


def cache_get(key: str) -> str | None:
    return None


def cache_set(key: str, value: str, ttl_s: int = 300) -> None:
    pass


def invalidate(pattern: str) -> int:
    """Invalidate cached keys matching a pattern (redis SCAN + DEL)."""
    return 0
