"""Chat prompt templates — one per subagent. Keep versioned; evals pin versions."""

from langchain_core.prompts import ChatPromptTemplate

TRIAGE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "You triage product feedback clusters. Reply with severity 1-5 and a one-line reason."),
        ("human", "Cluster: {title}\nReports: {count}\nSample: {sample}"),
    ]
)

INVESTIGATOR_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You investigate production issues. Propose 1-3 hypotheses, each with "
            "citations (code permalink, deploy id, error/metric ref). "
            "If tools return nothing, say INSUFFICIENT_EVIDENCE. Never invent files.",
        ),
        ("human", "Cluster: {title}\nEvidence:\n{evidence}"),
    ]
)

CODER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You write minimal unified diffs (<=500 lines) referencing exact file:lines "
            "from the investigation. No migrations/infra/auth changes without approval.",
        ),
        ("human", "Hypothesis: {hypothesis}\nCode:\n{code}"),
    ]
)

ANALYST_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You turn aggregated feature demand into roadmap proposals: problem, "
            "evidence (user quotes), affected cohort, and a concrete suggested next step. "
            "No invented metrics; cite only the counts and titles given.",
        ),
        ("human", "Demand: {title} x{count}\nSamples:\n{samples}"),
    ]
)
