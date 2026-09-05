"""Repo connect + grounded code search + GitHub webhook.

Depends on `pil_indexer` (pip install -e ../../workers/indexer).
`PIL_INDEX_ROOT` env overrides the on-disk index location.
"""

import hashlib
import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..auth import tenant_from_key
from ..ratelimit import check_rate_limit

router = APIRouter()


def _index_root() -> str:
    default = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                           "workers", "indexer", ".pil-index")
    return os.path.abspath(os.getenv("PIL_INDEX_ROOT", default))


def _lib():
    try:
        from pil_indexer.store import search_index
        from pil_indexer.sync import list_repos, sync_repo
        return sync_repo, list_repos, search_index
    except ImportError:
        return None


class SyncIn(BaseModel):
    repo_url: str = Field(min_length=1, max_length=500)
    alias: str | None = Field(default=None, max_length=100)


@router.post("/v1/repos/sync")
def sync_repo_endpoint(payload: SyncIn, tenant_id: str = Depends(tenant_from_key)):
    check_rate_limit(f"sync:{tenant_id}", limit=20)
    lib = _lib()
    if lib is None:
        raise HTTPException(status_code=501, detail="indexer not installed (pip install -e workers/indexer)")
    sync_repo_fn, _, _ = lib
    try:
        stats = sync_repo_fn(_index_root(), tenant_id, payload.repo_url, payload.alias)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"sync failed: {e}")
    return stats


@router.get("/v1/repos")
def list_repos_endpoint(tenant_id: str = Depends(tenant_from_key)):
    lib = _lib()
    if lib is None:
        raise HTTPException(status_code=501, detail="indexer not installed")
    _, list_repos_fn, _ = lib
    return {"items": list_repos_fn(_index_root(), tenant_id)}


@router.get("/v1/code/search")
def code_search_endpoint(
    q: str = Query(min_length=2, max_length=300),
    top_k: int = Query(default=8, le=20),
    tenant_id: str = Depends(tenant_from_key),
):
    lib = _lib()
    if lib is None:
        raise HTTPException(status_code=501, detail="indexer not installed")
    _, _, search_fn = lib
    return {"items": search_fn(_index_root(), tenant_id, q, top_k=top_k)}


@router.post("/v1/webhooks/github", status_code=202)
async def github_webhook(
    req: Request,
    tenant_id: str = Depends(tenant_from_key),
    x_github_event: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
):
    """GitHub App webhook: push -> re-index, pull_request -> accept (Phase 4 acts)."""
    raw = await req.body()
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if secret:
        if not x_hub_signature_256 or not x_hub_signature_256.startswith("sha256="):
            raise HTTPException(status_code=401, detail="missing signature")
        want = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(want, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="bad signature")
    try:
        payload = await req.json()
    except Exception:
        payload = {}
    if x_github_event == "ping":
        return {"status": "ok", "msg": "pong"}
    if x_github_event == "push":
        repo_url = ((payload.get("repository") or {}).get("clone_url") or "")
        if not repo_url:
            return {"status": "ignored", "reason": "no clone_url"}
        lib = _lib()
        if lib is None:
            return {"status": "accepted", "note": "indexer not installed; event logged"}
        sync_repo_fn, _, _ = lib
        try:
            stats = sync_repo_fn(_index_root(), tenant_id, repo_url)
        except Exception as e:
            return {"status": "accepted", "warning": f"re-index failed: {e}"}
        return {"status": "reindexed", **stats}
    if x_github_event == "pull_request":
        action = payload.get("action", "unknown")
        number = (payload.get("pull_request") or {}).get("number")
        return {"status": "accepted", "event": f"pull_request:{action}:{number}"}
    return {"status": "ignored", "reason": f"unhandled event {x_github_event}"}
