"""Deterministic investigation composer: evidence -> hypotheses.

Pure function over platform rows (no LLM, no I/O) so it runs identically in
unit tests, evals, and the API endpoint. The LangGraph nodes in graph.py
remain the durable-execution target; this module is the decision logic they
(and the API) share. Real LLMs upgrade wording later, never the math.
"""

from __future__ import annotations


def severity_of(title: str, count: int) -> int:
    t = (title or "").lower()
    sev = 2
    if any(k in t for k in ("crash", "500", "down", "payment", "checkout", "timeout")):
        sev = 4
    if count >= 30:
        sev = min(5, sev + 1)
    return sev


def investigate(cluster_key: str, title: str, count: int, members: list[dict],
                error_groups: list[dict], suspects: list[dict],
                code_hits: list[dict], service: str | None = None) -> dict:
    """Compose one investigation result with citations + confidence.

    Confidence (arch §8, local form): 0.5 + 0.15 telemetry match +
    0.15 deploy proximity + 0.10 code grounding, capped at 0.95.
    """
    service = service or ""
    groups = [g for g in error_groups if not service or g.get("service") == service]
    has_errors = bool(groups)
    has_deploy = bool(suspects)
    has_code = bool(code_hits)

    confidence = round(min(0.5 + 0.15 * has_errors + 0.15 * has_deploy
                           + 0.10 * has_code, 0.95), 2)
    severity = severity_of(title, count)

    code_refs = [h["ref"] for h in code_hits[:4] if h.get("ref")]
    top_error = groups[0] if groups else None

    hypotheses: list[dict] = []
    for s in suspects[:2]:
        d = s["deployment"]
        reason_bits = []
        if top_error:
            reason_bits.append(f"error '{top_error.get('title')}' x{top_error.get('count')} spikes")
        reason_bits.append(f"deploy {d.get('version')} {s.get('reason', '')}")
        if code_hits:
            reason_bits.append(f"code points at {code_hits[0].get('path')} :: {code_hits[0].get('symbol')}")
        hypotheses.append({
            "title": f"{d.get('service')} {d.get('version')} ({d.get('commit_sha')}) preceded spike",
            "confidence": confidence,
            "reason": "; ".join(reason_bits),
            "citations": code_refs + [f"pil://deployments/{d.get('id')}"]
            + ([f"pil://errors/{top_error.get('fingerprint')}"] if top_error else []),
            "contradicts": "",
            "deployment": d,
            "commit_sha": d.get("commit_sha"),
        })

    if not hypotheses and top_error:
        hypotheses.append({
            "title": f"undetermined deploy; top error '{top_error.get('title')}' x{top_error.get('count')}",
            "confidence": round(min(0.5 + 0.15 + 0.10 * has_code, 0.95), 2),
            "reason": "telemetry matches reports but no deploy in window",
            "citations": code_refs + [f"pil://errors/{top_error.get('fingerprint')}"],
            "contradicts": "",
            "deployment": None,
            "commit_sha": None,
        })
        confidence = hypotheses[0]["confidence"]

    if not hypotheses:
        return {"cluster_key": cluster_key, "status": "needs_info",
                "severity": severity, "confidence": 0.3, "hypotheses": [],
                "repro_steps": [], "service": service}

    top = hypotheses[0]
    version = (top["deployment"] or {}).get("version", "current")
    err_msg = top_error.get("title", "the reported error") if top_error else "the reported error"
    repro = [
        f"Deploy {service} version {version} to staging",
        f"Reproduce: {title}",
        f"Observe: {err_msg}",
    ]
    return {"cluster_key": cluster_key, "status": "hypothesized",
            "severity": severity, "confidence": confidence,
            "hypotheses": hypotheses, "repro_steps": repro, "service": service}
