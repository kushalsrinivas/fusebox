import os


def parse_api_keys(raw: str | None) -> dict[str, str]:
    """Parse 'key:tenant-id,key2:tenant2' into {key: tenant_id}."""
    mapping: dict[str, str] = {}
    if not raw:
        return mapping
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        k, v = pair.split(":", 1)
        mapping[k.strip()] = v.strip()
    return mapping


API_KEYS = parse_api_keys(
    os.getenv("API_KEYS", "dev-key:00000000-0000-0000-0000-000000000001")
)
DATABASE_URL = os.getenv("DATABASE_URL", "")
REDPANDA_BROKERS = os.getenv("REDPANDA_BROKERS", "")
