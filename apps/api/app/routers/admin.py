"""Admin: plan management + tenant purge. Gated by PIL_ADMIN_KEY."""

import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .. import db

router = APIRouter()


def _index_root() -> Path:
    here = os.path.dirname(__file__)
    return Path(os.path.abspath(os.getenv(
        "PIL_INDEX_ROOT",
        os.path.join(here, "..", "..", "..", "workers", "indexer", ".pil-index"))))


def _graph_root() -> Path:
    here = os.path.dirname(__file__)
    return Path(os.path.abspath(os.getenv(
        "PIL_GRAPH_ROOT",
        os.path.join(here, "..", "..", "..", "workers", "graph", ".pil-graph"))))


def _guard(x_admin_key: str | None = Header(default=None)) -> None:
    want = os.getenv("PIL_ADMIN_KEY", "")
    if not want or x_admin_key != want:
        raise HTTPException(status_code=403, detail="admin only")


class PlanIn(BaseModel):
    tenant_id: str = Field(min_length=1)
    plan: str = Field(pattern="^(free|pro|enterprise)$")


@router.post("/v1/admin/plan", dependencies=[Depends(_guard)])
def set_plan(payload: PlanIn):
    db.set_plan(payload.tenant_id, payload.plan)
    db.log_audit(payload.tenant_id, "admin", "plan_changed", {"plan": payload.plan})
    return {"tenant_id": payload.tenant_id, "plan": payload.plan}


@router.delete("/v1/admin/tenants/{tid}", dependencies=[Depends(_guard)])
def purge_tenant(tid: str):
    removed = db.purge_tenant(tid)
    files_removed: list[str] = []
    for target in (_index_root() / tid, _index_root() / ".cache" / tid,
                   _graph_root() / tid):
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            files_removed.append(str(target))
    return {"tenant_id": tid, "db_removed": removed, "files_removed": files_removed}
