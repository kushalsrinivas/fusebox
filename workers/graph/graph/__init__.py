"""Product knowledge graph: deterministic edges from platform rows.

Node kinds: feedback, cluster, error_group, deployment, code_unit, service.
Edge kinds (deterministic): IN_CLUSTER, AFFECTS_SERVICE, EMITTED_BY,
DEPLOYED_AS, LIKELY_CAUSED_BY (agent hypothesis: confidence + created_by).

File-backed JSON per tenant (`<root>/<tenant>/graph.json`); Neo4j replaces
`Graph.save/load` later — node/edge schema stays identical.
"""

from __future__ import annotations

import json
from pathlib import Path

NODE_KINDS = {"feedback", "cluster", "error_group", "deployment",
              "code_unit", "service"}


class Graph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []

    # -- writes ---------------------------------------------------------
    def upsert_node(self, kind: str, key: str, props: dict | None = None) -> str:
        assert kind in NODE_KINDS, kind
        nid = f"{kind}:{key}"
        self.nodes[nid] = {"id": nid, "kind": kind, "key": key,
                           **(props or {})}
        return nid

    def add_edge(self, src: str, kind: str, dst: str, props: dict | None = None) -> None:
        if any(e["src"] == src and e["kind"] == kind and e["dst"] == dst
               for e in self.edges):
            return
        self.edges.append({"src": src, "kind": kind, "dst": dst, **(props or {})})

    def hypothesize(self, src: str, dst: str, confidence: float, reason: str) -> None:
        self.add_edge(src, "LIKELY_CAUSED_BY", dst,
                      {"confidence": confidence, "reason": reason,
                       "created_by": "agent"})

    # -- reads ----------------------------------------------------------
    def neighbors(self, nid: str, kind: str | None = None) -> list[dict]:
        out = []
        for e in self.edges:
            if e["src"] == nid and (kind is None or e["kind"] == kind):
                out.append({**self.nodes.get(e["dst"], {"id": e["dst"]}), "_edge": e})
            elif e["dst"] == nid and (kind is None or e["kind"] == kind):
                out.append({**self.nodes.get(e["src"], {"id": e["src"]}), "_edge": e})
        return out

    # -- persistence ----------------------------------------------------
    def save(self, root: str, tenant: str) -> str:
        d = Path(root) / tenant
        d.mkdir(parents=True, exist_ok=True)
        f = d / "graph.json"
        f.write_text(json.dumps({"nodes": self.nodes, "edges": self.edges}))
        return str(f)

    @classmethod
    def load(cls, root: str, tenant: str) -> "Graph":
        g = cls()
        f = Path(root) / tenant / "graph.json"
        if f.exists():
            data = json.loads(f.read_text())
            g.nodes = data.get("nodes", {})
            g.edges = data.get("edges", [])
        return g


def build_graph(clusters: list[dict], feedback: list[dict],
                error_groups: list[dict], deploys: list[dict],
                code_hits: list[dict] | None = None) -> Graph:
    """Deterministic build from platform rows. No LLM, no I/O."""
    g = Graph()
    for c in clusters:
        # Node key is the stable cluster key (not the uuid): timelines and
        # hypothesis edges address clusters by key.
        ckey = c.get("key") or c.get("id")
        cid = g.upsert_node("cluster", ckey,
                            {"id": c.get("id"), "title": c.get("title", ""),
                             "count": c.get("count", 0),
                             "service_hint": c.get("service_hint")})
        if c.get("service_hint"):
            sid = g.upsert_node("service", c["service_hint"], {})
            g.add_edge(cid, "AFFECTS_SERVICE", sid, {"created_by": "worker"})
    for f in feedback:
        fid = g.upsert_node("feedback", f["id"], {"title": f.get("title", "")})
        for c in clusters:
            if f["id"] in c.get("members", c.get("member_ids", [])):
                g.add_edge(fid, "IN_CLUSTER",
                           f"cluster:{c.get('key') or c.get('id')}",
                           {"created_by": "worker"})
    for e in error_groups:
        eid = g.upsert_node("error_group", e["fingerprint"],
                            {"title": e.get("title", ""), "count": e.get("count", 0)})
        sid = g.upsert_node("service", e.get("service", "unknown"), {})
        g.add_edge(eid, "EMITTED_BY", sid, {"created_by": "worker"})
    for d in deploys:
        did = g.upsert_node("deployment", d["id"],
                            {"service": d.get("service"), "version": d.get("version"),
                             "commit_sha": d.get("commit_sha"),
                             "deployed_at": d.get("deployed_at")})
        sid = g.upsert_node("service", d.get("service", "unknown"), {})
        g.add_edge(did, "DEPLOYED_AS", sid, {"created_by": "worker"})
    for h in code_hits or []:
        uid = g.upsert_node("code_unit", f"{h.get('repo')}/{h.get('path')}#{h.get('symbol')}",
                            {"path": h.get("path"), "symbol": h.get("symbol"),
                             "ref": h.get("ref")})
        if h.get("service"):
            g.add_edge(uid, "IMPLEMENTS",
                       f"service:{h['service']}", {"created_by": "worker"})
    return g


def timeline(g: Graph, cluster_key: str) -> list[dict]:
    """Evidence timeline for a cluster: members, service errors, deploys, code.

    Ordered: reports -> errors -> deploys -> code -> hypotheses.
    """
    cid = f"cluster:{cluster_key}"
    if cid not in g.nodes:
        return []
    events: list[dict] = []
    for n in g.neighbors(cid, "IN_CLUSTER"):
        if n["kind"] == "feedback":
            events.append({"kind": "report", "ref": n["id"],
                           "excerpt": n.get("title", "")})
    for n in g.neighbors(cid, "AFFECTS_SERVICE"):
        if n["kind"] != "service":
            continue
        sid = n["id"]
        for m in g.neighbors(sid, "EMITTED_BY"):
            if m["kind"] == "error_group":
                events.append({"kind": "error", "ref": m["id"],
                               "excerpt": f"{m.get('title')} x{m.get('count')}"})
        for m in g.neighbors(sid, "DEPLOYED_AS"):
            if m["kind"] == "deployment":
                events.append({"kind": "deploy", "ref": m["id"],
                               "excerpt": f"{m.get('version')} @ {m.get('commit_sha')}"})
        for m in g.neighbors(sid, "IMPLEMENTS"):
            if m["kind"] == "code_unit":
                events.append({"kind": "code", "ref": m.get("ref", m["id"]),
                               "excerpt": f"{m.get('path')} :: {m.get('symbol')}"})
    for n in g.neighbors(cid, "LIKELY_CAUSED_BY"):
        e = n["_edge"]
        events.append({"kind": "hypothesis", "ref": n["id"],
                       "excerpt": f"{e.get('reason')} (conf {e.get('confidence')})"})
    order = {"report": 0, "error": 1, "deploy": 2, "code": 3, "hypothesis": 4}
    events.sort(key=lambda e: order.get(e["kind"], 9))
    return events
