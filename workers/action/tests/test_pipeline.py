from action.risk import score_risk
from action.sandbox import run_checks
from action.secrets import scan_diff

BASE = {"apps/payments/checkout.py": "def charge():\n    return 1\n"}

GOOD = """--- a/apps/payments/checkout.py
+++ b/apps/payments/checkout.py
@@ -1,2 +1,2 @@
 def charge():
-    return 1
+    return 2
"""

BROKEN = """--- a/apps/payments/checkout.py
+++ b/apps/payments/checkout.py
@@ -1,2 +1,2 @@
 def charge():
-    return 1
+    return (1 +
"""


def test_sandbox_passes_clean_diff():
    res = run_checks(BASE, GOOD)
    assert res["ok"] and res["applied"] == ["apps/payments/checkout.py"], res
    # syntax ran; tests honestly report they did not.
    assert res["levels"] == {"syntax": "passed", "tests": "not_run"}


def test_sandbox_runs_configured_tests():
    res = run_checks(BASE, GOOD, extra_checks=[["python3", "-c", "pass"]])
    assert res["ok"] and res["levels"]["tests"] == "passed"
    res = run_checks(BASE, GOOD, extra_checks=[["python3", "-c", "import sys; sys.exit(1)"]])
    assert not res["ok"] and res["levels"]["tests"] == "failed"


def test_sandbox_fails_syntax_error():
    res = run_checks(BASE, BROKEN)
    assert not res["ok"], res


def test_risk_low_for_isolated_small_diff():
    r = score_risk(["apps/exports/csv.py"], refcounts={}, diff_lines=5)
    assert r["level"] == "low" and not r["requires_two_approvals"]


def test_risk_high_for_sensitive_hub():
    r = score_risk(["apps/payments/checkout.py"],
                   refcounts={"apps/payments/checkout.py": 12}, diff_lines=250)
    assert r["level"] == "high" and r["requires_two_approvals"]
    assert any("fan-out" in f for f in r["factors"])


def test_secrets_scan_blocks_token():
    diff = GOOD + '+token = "sk-abc123XYZ456789"\n'
    hits = scan_diff(diff)
    assert hits and hits[0]["kind"] == "api token"
    assert scan_diff(GOOD) == []
