"""Thin tenant-scoped client for the PIL platform API.

Tools use this when `PIL_API_URL` + `PIL_API_KEY` are set (service/CI with a
live gateway); otherwise they fall back to deterministic stubs. The optional
`_client` parameter is the test seam (pass an httpx client on ASGI transport).
"""

from __future__ import annotations

import os
from typing import Any


def _base() -> tuple[str, str] | None:
    url = os.getenv("PIL_API_URL", "")
    key = os.getenv("PIL_API_KEY", "")
    return (url, key) if url and key else None


def _get(path: str, params: dict, _client: Any | None = None) -> Any | None:
    cfg = _base()
    if cfg is None and _client is None:
        return None
    import httpx

    try:
        if _client is not None:
            r = _client.get(path, params=params)
        else:
            assert cfg is not None
            url, key = cfg
            with httpx.Client(base_url=url, headers={"X-API-Key": key},
                              timeout=10) as client:
                r = client.get(path, params=params)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def get_deploys(service: str, _client: Any | None = None) -> list[dict] | None:
    data = _get("/v1/deploys", {"service": service, "limit": 50}, _client)
    return data["items"] if isinstance(data, dict) else None


def get_error_groups(service: str, _client: Any | None = None) -> list[dict] | None:
    data = _get("/v1/errors/groups", {"service": service, "limit": 20}, _client)
    return data["items"] if isinstance(data, dict) else None


def get_correlation(service: str, spike_start: str,
                    _client: Any | None = None) -> dict | None:
    data = _get("/v1/correlate", {"service": service, "spike_start": spike_start},
                _client)
    return data if isinstance(data, dict) else None
