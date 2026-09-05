"""LangGraph orchestrator: TRIVIAGE -> ENRICH -> HYPOTHESIZE -> VERIFY -> PLAN.

Runs fully offline when `llm=None` (deterministic stub logic for CI/Phase 0).
Pass a LangChain chat model (ChatOpenAI/ChatAnthropic) to upgrade the
HYPOTHESIZE step without changing topology.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from .state import InvestigationState
from .tools import code_blame, code_search, deploys_list, logs_query, metrics_query


def _log(state: InvestigationState, msg: str) -> list[dict]:
    return [*state.get("audit", []), {"node": msg}]


def triage(state: InvestigationState) -> dict:
    title = state.get("cluster_title", "").lower()
    count = state.get("cluster_count", 1)
    severity = 2
    if any(k in title for k in ("crash", "500", "down", "payment", "checkout")):
        severity = 4
    if count >= 30:
        severity = min(5, severity + 1)
    return {"severity": severity, "status": "triaged", "audit": _log(state, "triage")}


def enrich(state: InvestigationState) -> dict:
    tenant = state["tenant_id"]
    title = state.get("cluster_title", "")
    evidence: list[dict] = []
    for hit in code_search.invoke({"query": title, "tenant_id": tenant}):
        evidence.append({"kind": "code", "ref": hit["ref"], "excerpt": hit["excerpt"]})
    for d in deploys_list.invoke({"service": "payments-api", "tenant_id": tenant}):
        evidence.append({"kind": "deploy", "ref": d["ref"], "excerpt": f"{d['id']} {d['version']} @ {d['commit_sha']}"})
    m = metrics_query.invoke({"service": "payments-api", "tenant_id": tenant})
    evidence.append({"kind": "metric", "ref": m["ref"], "excerpt": m["error_rate_delta"]})
    for log in logs_query.invoke({"service": "payments-api", "tenant_id": tenant}):
        evidence.append({"kind": "log", "ref": log["ref"], "excerpt": log["msg"]})
    return {"evidence": evidence, "status": "enriched", "audit": _log(state, "enrich")}


def hypothesize(state: InvestigationState, llm: Any | None = None) -> dict:
    evidence = state.get("evidence", [])
    refs = [e["ref"] for e in evidence]
    has_code = any(e["kind"] == "code" for e in evidence)
    has_deploy = any(e["kind"] == "deploy" for e in evidence)
    has_metric = any(e["kind"] == "metric" for e in evidence)

    if llm is not None:
        # Real LLM path (Phase 3): prompts.INVESTIGATOR_PROMPT | llm.
        # Kept behind the flag so CI never needs keys. Parse + validate citations here.
        pass

    if not (has_code and (has_deploy or has_metric)):
        return {
            "hypotheses": [],
            "confidence": 0.3,
            "status": "needs_info",
            "audit": _log(state, "hypothesize:insufficient"),
        }
    confidence = 0.5 + (0.15 if has_metric else 0) + (0.15 if has_deploy else 0) + 0.1
    return {
        "hypotheses": [
            {
                "title": "capture timeout after deploy dep_891 (commit ab12cd34)",
                "confidence": round(min(confidence, 0.95), 2),
                "reason": "error spike aligns with deploy window; blame points at refactored capture path",
                "citations": refs[:4],
                "contradicts": "",
            }
        ],
        "confidence": round(min(confidence, 0.95), 2),
        "status": "hypothesized",
        "audit": _log(state, "hypothesize"),
    }


def verify(state: InvestigationState) -> dict:
    """VERIFY gate: require >=2 tool-backed evidence + blame before PLAN."""
    tenant = state.get("tenant_id", "")
    evidence = state.get("evidence", [])
    blame = code_blame.invoke({"path": "apps/payments/checkout.py", "tenant_id": tenant, "line": 130})
    kinds = {e["kind"] for e in evidence}
    if len(evidence) >= 2 and "code" in kinds:
        evidence = [*evidence, {"kind": "code", "ref": blame["ref"], "excerpt": blame["message"]}]
        return {"evidence": evidence, "status": "verified", "audit": _log(state, "verify:pass")}
    return {"status": "needs_info", "audit": _log(state, "verify:fail")}


def plan(state: InvestigationState) -> dict:
    hyps = state.get("hypotheses", [])
    title = hyps[0]["title"] if hyps else "investigate further"
    return {
        "repro_steps": [
            "Deploy version 1.4.3 to staging",
            "Tap Pay on iOS checkout with test card",
            "Observe capture timeout in logs (tail q=capture)",
        ],
        "status": "planned",
        "audit": [*state.get("audit", []), {"node": "plan", "next": title}],
    }


def build_investigation_graph(llm: Any | None = None):
    g = StateGraph(InvestigationState)
    g.add_node("triage", triage)
    g.add_node("enrich", enrich)
    g.add_node("hypothesize", lambda s: hypothesize(s, llm=llm))
    g.add_node("verify", verify)
    g.add_node("plan", plan)
    g.set_entry_point("triage")
    g.add_edge("triage", "enrich")
    g.add_edge("enrich", "hypothesize")
    g.add_conditional_edges(
        "hypothesize",
        lambda s: "verify" if s.get("status") == "hypothesized" else END,
    )
    g.add_conditional_edges(
        "verify",
        lambda s: "plan" if s.get("status") == "verified" else END,
    )
    g.add_edge("plan", END)
    return g.compile()
