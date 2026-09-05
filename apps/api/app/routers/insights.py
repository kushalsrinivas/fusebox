"""Product insights: feature digest, proposals, metrics, signals, replay."""

import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db
from ..auth import tenant_from_key

router = APIRouter()


def _roots():
    here = os.path.dirname(__file__)
    idx = os.path.abspath(os.getenv(
        "PIL_INDEX_ROOT",
        os.path.join(here, "..", "..", "..", "workers", "indexer", ".pil-index")))
    return idx


def _digest(tenant_id: str, top_n: int = 10) -> list[dict]:
    try:
        from insights import build_digest
    except ImportError:
        raise HTTPException(status_code=501, detail="insights lib not installed")
    clusters = [{**c, "members": c["member_ids"]} for c in db.list_clusters(tenant_id)]
    feedback = db.list_feedback(tenant_id, 10000)
    fb_map = {f["id"]: f for f in feedback}
    return build_digest(clusters, fb_map, top_n)


@router.get("/v1/insights/digest")
def insights_digest(top_n: int = 10, tenant_id: str = Depends(tenant_from_key)):
    return {"items": _digest(tenant_id, top_n)}


@router.get("/v1/insights/proposals")
def insights_proposals(top_n: int = 10, tenant_id: str = Depends(tenant_from_key)):
    try:
        from agent.analyst import render_proposals
    except ImportError:
        raise HTTPException(status_code=501, detail="agent lib not installed")
    return {"items": render_proposals(_digest(tenant_id, top_n))}


@router.get("/v1/metrics/summary")
def metrics_summary(tenant_id: str = Depends(tenant_from_key)):
    feedback = db.list_feedback(tenant_id, 100000)
    actions = db.list_actions(tenant_id)
    verifs = db.list_verifications(tenant_id)
    by_status: dict[str, int] = {}
    for a in actions:
        by_status[a["status"]] = by_status.get(a["status"], 0) + 1
    v_by_status: dict[str, int] = {}
    for v in verifs:
        v_by_status[v["status"]] = v_by_status.get(v["status"], 0) + 1
    approved = by_status.get("approved", 0)
    return {
        "plan": db.get_plan(tenant_id),
        "usage": {k: db.usage_used(tenant_id, k)
                 for k in ("feedback", "investigations", "actions")},
        "feedback": len(feedback),
        "clusters": len(db.list_clusters(tenant_id)),
        "actions_by_status": by_status,
        "verifications_by_status": v_by_status,
        "pr_acceptance": {
            "approved": approved,
            "proposed_total": sum(by_status.values()),
            "rate": round(approved / sum(by_status.values()), 3) if by_status else 0.0,
        },
        "signals": db.signal_summary(tenant_id),
    }


class SignalIn(BaseModel):
    signal: str = Field(min_length=1, max_length=32)
    note: str = Field(default="", max_length=2000)


@router.post("/v1/investigations/{iid}/feedback", status_code=202)
def post_signal(iid: str, payload: SignalIn, tenant_id: str = Depends(tenant_from_key)):
    try:
        row = db.save_signal(tenant_id, iid, payload.signal, payload.note)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"id": row["id"], "status": "accepted"}


@router.get("/v1/signals/summary")
def get_signal_summary(tenant_id: str = Depends(tenant_from_key)):
    return {"signals": db.signal_summary(tenant_id)}


@router.post("/v1/admin/replay")
def replay(tenant_id: str = Depends(tenant_from_key)):
    """Rebuild derived stores (index, clusters, graph) from source data.

    One command to regenerate every projection after a wipe or upgrade.
    """
    try:
        from pil_indexer.sync import sync_repo
    except ImportError:
        raise HTTPException(status_code=501, detail="indexer lib not installed")
    root = _roots()
    base = Path(root) / tenant_id
    stats: list[dict] = []
    if base.exists():
        for meta in sorted(base.glob("*/meta.json")):
            try:
                repo_url = json.loads(meta.read_text()).get("repo_url")
            except (OSError, ValueError):
                continue
            if not repo_url:
                continue
            try:
                stats.append(sync_repo(root, tenant_id, repo_url, alias=meta.parent.name))
            except Exception as e:  # noqa: BLE001
                stats.append({"repo": meta.parent.name, "error": str(e)[:200]})
    try:
        from ingest.grouping import group_feedback
        rows = db.list_feedback(tenant_id, 10000)
        items = [{"id": r["id"], "title": r["title"], "body": r.get("body", ""),
                  "service_hint": r.get("service_hint")} for r in rows]
        clusters = db.replace_clusters(tenant_id, group_feedback(items))
    except ImportError:
        clusters = []
    try:
        from graph import build_graph
        adapted = [{**c, "members": c["member_ids"]} for c in db.list_clusters(tenant_id)]
        g = build_graph(adapted, db.list_feedback(tenant_id, 10000),
                        db.list_error_groups(tenant_id),
                        db.list_deployments(tenant_id, None, 200))
        graph_root = os.path.abspath(os.getenv(
            "PIL_GRAPH_ROOT",
            os.path.join(os.path.dirname(__file__), "..", "..", "..",
                         "workers", "graph", ".pil-graph")))
        g.save(graph_root, tenant_id)
        graph_stats = {"nodes": len(g.nodes), "edges": len(g.edges)}
    except ImportError:
        graph_stats = {"nodes": 0, "edges": 0}
    return {"reindexed": stats, "clusters": len(clusters), "graph": graph_stats}
