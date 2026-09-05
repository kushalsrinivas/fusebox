"""Service entrypoint: run one investigation over an IssueCluster."""

from __future__ import annotations

from typing import Any

from .graph import build_investigation_graph


def run_investigation(
    tenant_id: str,
    cluster_id: str,
    cluster_title: str,
    cluster_count: int = 1,
    llm: Any | None = None,
) -> dict:
    graph = build_investigation_graph(llm=llm)
    result = graph.invoke(
        {
            "tenant_id": tenant_id,
            "cluster_id": cluster_id,
            "cluster_title": cluster_title,
            "cluster_count": cluster_count,
            "evidence": [],
            "hypotheses": [],
            "audit": [],
        }
    )
    return result


def make_llm(provider: str = "openai", model: str = "gpt-4o-mini"):
    """Optional real-model factory. Requires provider API keys; unused in CI."""
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, temperature=0)
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, temperature=0)
    raise ValueError(f"unknown provider {provider}")
