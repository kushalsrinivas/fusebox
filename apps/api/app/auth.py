from fastapi import Header, HTTPException

from .config import API_KEYS

DEMO_TENANT = "00000000-0000-0000-0000-000000000001"


def tenant_from_key(x_api_key: str | None = Header(default=None)) -> str:
    if not x_api_key or x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="invalid api key")
    return API_KEYS[x_api_key]
