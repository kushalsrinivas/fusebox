"""Liveness + deploy version endpoint."""


def health() -> dict:
    return {"ok": True}


def version() -> dict:
    """Return the running deploy version (set at build time)."""
    return {"version": "1.4.3", "commit": "ab12cd34"}
