"""Shared investigation state for the LangGraph orchestrator.

One run = one IssueCluster. State is checkpointable (persist to Postgres
`investigations` table in Phase 3; in-memory for Phase 0 skeleton).
"""

from __future__ import annotations

from typing import TypedDict


class Evidence(TypedDict, total=False):
    kind: str  # code | deploy | error | metric | log | trace
    ref: str  # permalink / event id / query hash
    excerpt: str


class Hypothesis(TypedDict, total=False):
    title: str
    confidence: float
    reason: str
    citations: list[str]
    contradicts: str


class InvestigationState(TypedDict, total=False):
    tenant_id: str
    cluster_id: str
    cluster_title: str
    cluster_count: int
    severity: int
    evidence: list[Evidence]
    hypotheses: list[Hypothesis]
    confidence: float
    status: str  # triaged | enriched | hypothesized | verified | planned | needs_info
    repro_steps: list[str]
    audit: list[dict]
