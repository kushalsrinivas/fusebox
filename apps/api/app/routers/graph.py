"""Knowledge-graph endpoints: rebuild snapshot + read timelines."""

import os

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import db
from ..auth import tenant_from_key

router = APIRouter()


def _graph_root() -> str:
    default = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                           "workers", "graph", ".pil-graph")
    return os.path.abspath(os.getenv("PIL_GRAPH_ROOT", default))


@router.post("/v1/graph/rebuild")
def rebuild_graph(tenant_id: str = Depends(tenant_from_key)):
    try:
        from graph import build_graph
    except ImportError:
        raise HTTPException(status_code=501, detail="graph lib not installed")
    clusters = [{**c, "members": c["member_ids"]} for c in db.list_clusters(tenant_id)]
    feedback = db.list_feedback(tenant_id, 1000)
    g = build_graph(clusters, feedback, db.list_error_groups(tenant_id),
                    db.list_deployments(tenant_id, None, 200))
    path = g.save(_graph_root(), tenant_id)
    return {"nodes": len(g.nodes), "edges": len(g.edges), "path": path}


@router.get("/v1/graph/timeline")
def graph_timeline(cluster_key: str = Query(min_length=1),
                   tenant_id: str = Depends(tenant_from_key)):
    try:
        from graph import Graph, timeline
    except ImportError:
        raise HTTPException(status_code=501, detail="graph lib not installed")
    return {"items": timeline(Graph.load(_graph_root(), tenant_id), cluster_key)}
