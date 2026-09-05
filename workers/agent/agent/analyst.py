"""Product analyst: digest -> proposal docs (deterministic render, no LLM).

LLMs upgrade the prose later; the structure (problem, evidence, cohort,
suggested next step) is fixed so roadmap tooling can parse it.
"""

from __future__ import annotations

from .prompts import ANALYST_PROMPT  # noqa: F401  (versioned prompt for the LLM upgrade)


def render_proposals(digest: list[dict]) -> list[dict]:
    proposals = []
    for d in digest:
        cohort = f"{d['requests']} request(s)" + (
            f" around `{d['service_hint']}`" if d.get("service_hint") else "")
        proposals.append({
            "cluster_key": d["cluster_key"],
            "title": f"Proposal: {d['title']}",
            "problem": f"Users repeatedly ask for '{d['title']}' ({cohort}).",
            "evidence": d["sample_titles"],
            "suggested_next": "Scope MVP in Linear; attach this digest as context.",
            "markdown": "\n".join([
                f"## Proposal: {d['title']}",
                "",
                f"**Demand:** {d['requests']} requests "
                f"(feature ratio {d['feature_ratio']}).",
                "",
                "**Sample asks:**",
                *[f"- {t}" for t in d["sample_titles"]],
                "",
                "**Suggested next:** Scope MVP in Linear; attach this digest as context.",
            ]),
        })
    return proposals
