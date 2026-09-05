"""Action pipeline evals: 9 propose/approve scenarios over the real lib fns.

Mirrors the API decision order (validate -> secrets -> sandbox -> risk)
without a server. Bar: >=8/9 correct decisions.

Run: `python evals/run_action_evals.py [--min-pass 8]` from workers/action.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from action.diff import changed_paths, diff_size, parse_diff, validate_diff  # noqa: E402
from action.risk import score_risk  # noqa: E402
from action.sandbox import run_checks  # noqa: E402
from action.secrets import scan_diff  # noqa: E402

BASE = {
    "apps/payments/checkout.py": "def charge():\n    return _gateway.capture(a)\n",
    "apps/auth/login.py": "def login():\n    return True\n",
    "apps/exports/csv.py": "def export(rows):\n    return 'csv'\n",
}

CLEAN = """--- a/apps/payments/checkout.py
+++ b/apps/payments/checkout.py
@@ -1,2 +1,2 @@
 def charge():
-    return _gateway.capture(a)
+    return _gateway.capture(a, timeout_ms=5000)
"""

BROKEN = CLEAN.replace("+    return _gateway.capture(a, timeout_ms=5000)",
                       "+    return _gateway.capture((a")


def decide(diff: str, refcounts: dict | None = None) -> dict:
    issues = validate_diff(diff)
    if issues:
        return {"decision": "reject", "why": issues}
    if scan_diff(diff):
        return {"decision": "reject", "why": ["secrets in diff"]}
    sandbox = run_checks(BASE, diff)
    if not sandbox["ok"]:
        return {"decision": "validation_failed", "why": sandbox["logs"]}
    paths = changed_paths(parse_diff(diff))
    risk = score_risk(paths, refcounts or {}, diff_lines=diff_size(diff))
    return {"decision": "approve_candidate", "risk": risk, "sandbox": sandbox["ok"]}


def SCENARIOS():
    new_file = ("new file diff applies",
                "--- /dev/null\n+++ b/apps/cache/flag.py\n@@ -0,0 +1,2 @@\n+ENABLED = True\n+",
                "approve_candidate", None)
    big = ("oversized diff rejected", CLEAN + "".join(f"+x{i}\n" for i in range(600)),
           "reject", None)
    return [
        ("clean isolated fix passes", CLEAN, "approve_candidate", {}),
        ("denylisted auth path rejected",
         CLEAN.replace("apps/payments/checkout.py", "apps/auth/login.py"), "reject", None),
        ("secret in diff rejected", CLEAN + '+k = "sk-abc123XYZ456789"\n', "reject", None),
        ("syntax-broken diff fails validation", BROKEN, "validation_failed", None),
        new_file, big,
        ("unsafe path rejected",
         CLEAN.replace("a/apps/payments/checkout.py", "a/../evil.py"), "reject", None),
        ("hub module scores high risk", CLEAN, "approve_candidate",
         {"apps/payments/checkout.py": 14}),
        ("deletion diff parses", "--- a/apps/exports/csv.py\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-def export(rows):\n-    return 'csv'\n",
         "approve_candidate", {}),
    ]


def run_evals():
    results = []
    for name, diff, expected, refcounts in SCENARIOS():
        try:
            got = decide(diff, refcounts)["decision"]
        except Exception as e:  # noqa: BLE001
            got = f"error: {e}"
        results.append({"scenario": name, "expected": expected, "got": got,
                        "pass": got == expected})
    # risk assertion lives outside decide()
    r = score_risk(["apps/payments/checkout.py"],
                   {"apps/payments/checkout.py": 14}, diff_lines=250)
    results.append({"scenario": "hub module high risk + two approvals",
                    "expected": True,
                    "got": r["level"] == "high" and r["requires_two_approvals"],
                    "pass": r["level"] == "high" and r["requires_two_approvals"]})
    passed = sum(1 for x in results if x["pass"])
    return {"passed": passed, "total": len(results), "results": results}


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-pass", type=int, default=8)
    args = ap.parse_args()
    rep = run_evals()
    print(f"EVAL actions: {rep['passed']}/{rep['total']} (bar {args.min_pass})")
    for r in rep["results"]:
        print(f"  [{'PASS' if r['pass'] else 'FAIL'}] {r['scenario']} -> {r['got']}")
    if rep["passed"] < args.min_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
