"""LangChain tool definitions — the ONLY way the agent touches data.

Phase 0: deterministic stubs returning canned evidence so the graph runs
offline and in CI with no API keys. Phase 1+ swaps each body for a real
implementation (Qdrant / Neo4j / Grafana / Loki / GitHub) keeping the same
name + args so prompts and evals don't churn.

Every call appends to the investigation audit log (who/when/args).
"""

from __future__ import annotations

import os

from langchain_core.tools import tool


def _real_search(query: str, tenant_id: str, top_k: int) -> list[dict] | None:
    """Hit the tenant's real repo index when available, else None (stub)."""
    root = os.getenv("PIL_INDEX_ROOT", "")
    if not root:
        return None
    try:
        from pil_indexer.store import search_index
    except ImportError:
        return None
    try:
        return search_index(root, tenant_id, query, top_k=top_k)
    except Exception:
        return None


def _real_read(path: str, tenant_id: str, start: int, end: int) -> dict | None:
    root = os.getenv("PIL_INDEX_ROOT", "")
    if not root:
        return None
    try:
        from pil_indexer.store import load
    except ImportError:
        return None
    try:
        best = None
        for c in load(root, tenant_id):
            if c["path"] == path or c["path"].endswith(path):
                if best is None or c["start_line"] <= start <= c["end_line"]:
                    best = c
        if best is None:
            return None
        lines = best["content"].splitlines()
        # content line 1 is the "# path :: symbol" header; code starts at 2
        code = lines[1:]
        lo, hi = max(start - best["start_line"], 0), end - best["start_line"] + 1
        return {
            "path": best["path"],
            "lines": f"{start}-{end}",
            "content": "\n".join(code[lo:hi]),
            "ref": f"index://{best['repo']}/{best['path']}#L{start}-L{end}",
        }
    except Exception:
        return None


@tool
def code_search(query: str, tenant_id: str, top_k: int = 8) -> list[dict]:
    """Search the tenant's indexed repos (real index when PIL_INDEX_ROOT is set, else stub)."""
    real = _real_search(query, tenant_id, top_k)
    if real:
        return [
            {"path": h["path"], "symbol": h["symbol"], "lines": h["lines"],
             "excerpt": h["excerpt"][:600], "ref": h["ref"]}
            for h in real
        ]
    return [
        {
            "path": "apps/payments/checkout.py",
            "symbol": "charge",
            "lines": "120-145",
            "excerpt": "def charge(...): ... gateway.capture() ...",
            "ref": "github://demo-repo/apps/payments/checkout.py#L120-L145",
        }
    ]


@tool
def code_read(path: str, tenant_id: str, start: int = 1, end: int = 60) -> dict:
    """Read exact file lines (real index when available, else stub)."""
    real = _real_read(path, tenant_id, start, end)
    if real:
        return real
    return {
        "path": path,
        "lines": f"{start}-{end}",
        "content": f"# stub contents of {path} lines {start}-{end}",
        "ref": f"github://demo-repo/{path}#L{start}-L{end}",
    }


@tool
def code_blame(path: str, tenant_id: str, line: int) -> dict:
    """Return suspect commit for a line (git blame in Phase 1; stub now)."""
    return {
        "path": path,
        "line": line,
        "commit_sha": "ab12cd34",
        "author": "dev@example.com",
        "message": "refactor capture flow",
        "ref": "github://demo-repo/commit/ab12cd34",
    }


@tool
def graph_query(cypher: str, tenant_id: str) -> list[dict]:
    """Run a read-only Cypher query against the knowledge graph (stub now)."""
    return [
        {
            "service": "payments-api",
            "deploy": "dep_891",
            "commit": "ab12cd34",
            "ref": "graph://deployment/dep_891",
        }
    ]


@tool
def metrics_query(service: str, tenant_id: str, window: str = "6h") -> dict:
    """Query error-rate/p99 window (Grafana/Prom in Phase 2; stub now)."""
    return {
        "service": service,
        "window": window,
        "error_rate_delta": "+9.4x vs prior 7d",
        "ref": f"grafana://{service}/error-rate?window={window}",
    }


@tool
def logs_query(service: str, tenant_id: str, window: str = "1h") -> list[dict]:
    """Fetch log tail (Loki/CloudWatch in Phase 2; stub now)."""
    return [
        {
            "ts": "2026-09-05T12:01:00Z",
            "level": "ERROR",
            "msg": "capture failed: timeout after 3000ms",
            "ref": "loki://payments-api/tail?q=capture",
        }
    ]


@tool
def deploys_list(service: str, tenant_id: str, since_hours: int = 6) -> list[dict]:
    """List recent deployments (live platform API when configured, else stub)."""
    from .platform import get_deploys

    live = get_deploys(service)
    if live:
        return [
            {**d, "ref": f"pil://deployments/{d.get('id')}"}
            for d in live
        ]
    return [
        {
            "id": "dep_891",
            "service": service,
            "version": "1.4.3",
            "commit_sha": "ab12cd34",
            "deployed_at": "2026-09-05T10:00:00Z",
            "ref": "github://demo-repo/deployments/dep_891",
        }
    ]


@tool
def errors_recent(service: str, tenant_id: str, limit: int = 10) -> list[dict]:
    """List recent error groups for a service (live API when configured, else stub)."""
    from .platform import get_error_groups

    live = get_error_groups(service)
    if live:
        return [
            {"fingerprint": g.get("fingerprint"), "title": g.get("title"),
             "service": g.get("service"), "count": g.get("count"),
             "last_seen": g.get("last_seen"),
             "ref": f"pil://errors/{g.get('fingerprint')}"}
            for g in live[:limit]
        ]
    return [
        {
            "fingerprint": "fp_capture_timeout",
            "title": "capture failed: timeout",
            "service": service,
            "count": 42,
            "last_seen": "2026-09-05T12:00:00Z",
            "ref": "sentry://issues/fp_capture_timeout",
        }
    ]


ALL_TOOLS = [
    code_search,
    code_read,
    code_blame,
    graph_query,
    metrics_query,
    logs_query,
    deploys_list,
    errors_recent,
]
