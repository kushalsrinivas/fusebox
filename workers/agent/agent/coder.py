"""Coder subagent seam: hypothesis + code -> unified diff.

Needs a LangChain chat model (service.make_llm). Without one, raises
NeedsLLMError — the platform never fabricates code. Output contract: the
model replies with one ```diff fenced block; we extract, sanity-check
(parseable, <=500 lines), and return it for the sandbox pipeline.
"""

from __future__ import annotations

import re

from .prompts import CODER_PROMPT

DIFF_FENCE = re.compile(r"```diff\n(.*?)```", re.DOTALL)
MAX_DIFF_LINES = 500


class NeedsLLMError(RuntimeError):
    pass


def generate_diff(hypothesis: str, code_context: str, llm=None) -> str:
    if llm is None:
        raise NeedsLLMError("coder requires a chat model (see service.make_llm)")
    messages = CODER_PROMPT.format_messages(hypothesis=hypothesis, code=code_context)
    reply = llm.invoke(messages)
    text = getattr(reply, "content", str(reply))
    m = DIFF_FENCE.search(text)
    if not m:
        raise ValueError("coder reply contained no ```diff block")
    diff = m.group(1).strip() + "\n"
    if len(diff.splitlines()) > MAX_DIFF_LINES:
        raise ValueError(f"coder diff too large ({len(diff.splitlines())} lines)")
    if not any(l.startswith(("--- ", "+++ ", "@@")) for l in diff.splitlines()):
        raise ValueError("coder diff has no unified-diff headers")
    return diff
