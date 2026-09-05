import pytest

from agent.coder import NeedsLLMError, generate_diff

DIFF = """--- a/apps/payments/checkout.py
+++ b/apps/payments/checkout.py
@@ -1,2 +1,2 @@
-    return 1
+    return 2
"""


class FakeLLM:
    def __init__(self, text):
        self.text = text

    def invoke(self, messages):
        assert messages, "coder must pass prompt messages"
        return type("Reply", (), {"content": self.text})()


def test_generate_diff_extracts_fence():
    llm = FakeLLM(f"explanation here\n```diff\n{DIFF}```\ntrailing")
    assert generate_diff("hyp", "code", llm) == DIFF


def test_generate_diff_needs_llm():
    with pytest.raises(NeedsLLMError):
        generate_diff("hyp", "code", None)


def test_generate_diff_rejects_no_fence():
    with pytest.raises(ValueError):
        generate_diff("hyp", "code", FakeLLM("just prose, no diff"))
