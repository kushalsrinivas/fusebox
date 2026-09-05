"""Issue clusters + investigations (Phase 3).

Rebuild groups feedback into clusters; investigate composes evidence
(errors, suspect deploys, code hits) into hypotheses via agent.runner,
persists the knowledge-graph snapshot, and stores the investigation.
"""

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from .. import db, quotas
from ..auth import tenant_from_key

router = APIRouter()


def _index_root() -> str:
    default = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                           "workers", "indexer", ".pil-index")
    return os.path.abspath(os.getenv("PIL_INDEX_ROOT", default))


def _graph_root() -> str:
    default = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                           "workers", "graph", ".pil-graph")
    return os.path.abspath(os.getenv("PIL_GRAPH_ROOT", default))


@router.post("/v1/clusters/rebuild")
def rebuild_clusters(tenant_id: str = Depends(tenant_from_key)):
    try:
        from ingest.grouping import group_feedback
    except ImportError:
        raise HTTPException(status_code=501, detail="ingest lib not installed")
    rows = db.list_feedback(tenant_id, 1000)
    items = [{"id": r["id"], "title": r["title"], "body": r.get("body", ""),
              "service_hint": r.get("service_hint")} for r in rows]
    clusters = group_feedback(items)
    return {"items": db.replace_clusters(tenant_id, clusters), "count": len(clusters)}


@router.get("/v1/clusters")
def get_clusters(tenant_id: str = Depends(tenant_from_key)):
    return {"items": db.list_clusters(tenant_id)}


@router.get("/v1/clusters/{cid}")
def get_cluster(cid: str, tenant_id: str = Depends(tenant_from_key)):
    cluster = db.get_cluster(tenant_id, cid)
    if cluster is None:
        raise HTTPException(status_code=404, detail="cluster not found")
    return {"cluster": cluster,
            "members": db.list_feedback_by_ids(tenant_id, cluster["member_ids"]),
            "investigation": db.latest_investigation(tenant_id, cluster["id"])}


def _spike_start(groups: list[dict]) -> str:
    if groups:
        return max(g["last_seen"] for g in groups)
    return datetime.now(timezone.utc).isoformat()


@router.post("/v1/clusters/{cid}/investigate")
def investigate_cluster(cid: str, tenant_id: str = Depends(tenant_from_key)):
    try:
        from agent.runner import investigate
    except ImportError:
        raise HTTPException(status_code=501, detail="agent lib not installed")
    cluster = db.get_cluster(tenant_id, cid)
    if cluster is None:
        raise HTTPException(status_code=404, detail="cluster not found")
    quotas.check("investigations", tenant_id)

    members = db.list_feedback_by_ids(tenant_id, cluster["member_ids"])
    service = cluster.get("service_hint")
    groups = db.list_error_groups(tenant_id, service) if service else []
    deploys = db.list_deployments(tenant_id, service, 200) if service else []

    suspects: list[dict] = []
    if service and deploys:
        try:
            from correlation import find_suspects
            suspects = find_suspects(deploys, _spike_start(groups), service)
        except ImportError:
            pass

    code_hits: list[dict] = []
    try:
        from pil_indexer.store import search_index
        code_hits = search_index(_index_root(), tenant_id, cluster["title"], top_k=8)
        for h in code_hits:
            h["service"] = service
    except Exception:
        code_hits = []

    result = investigate(cluster["key"], cluster["title"], cluster["count"],
                         members, groups, suspects, code_hits, service)

    # knowledge-graph snapshot: deterministic edges + hypothesis edges
    try:
        from graph import Graph, build_graph, timeline
        adapted = [{**cluster, "members": cluster["member_ids"]}]
        g = build_graph(adapted, members, groups, deploys, code_hits)
        for h in result["hypotheses"]:
            dep = h.get("deployment")
            if dep:
                g.hypothesize(f"cluster:{cluster['key']}",
                              f"deployment:{dep['id']}",
                              h["confidence"], h["reason"])
        g.save(_graph_root(), tenant_id)
        tl = timeline(g, cluster["key"])
    except ImportError:
        tl = []

    inv = db.save_investigation(tenant_id, cluster["id"], result)
    quotas.bump("investigations", tenant_id)
    return {"investigation_id": inv["id"], "result": result, "timeline": tl}
