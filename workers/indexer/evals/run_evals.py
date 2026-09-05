"""Grounded code-search evals: 20 natural queries over the fixture demo repo.

Pass = expected path appears in top-3 hits. Bar: >=16/20 (Phase 1 exit criteria).
Run: `python evals/run_evals.py [--min-pass 16]` from workers/indexer.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pil_indexer.store import search_index  # noqa: E402
from pil_indexer.sync import sync_repo  # noqa: E402

FIX = str(Path(__file__).parent.parent / "tests" / "fixtures" / "demo-repo")

# (query, expected substring of path)
QUERIES = [
    ("where is the checkout charge logic", "payments/checkout.py"),
    ("capture payment timeout after deploy", "payments/checkout.py"),
    ("refund flow for captured payments", "payments/checkout.py"),
    ("payment gateway capture client", "payments/gateway.py"),
    ("user login returns 500", "auth/login.py"),
    ("refresh token exchange", "auth/login.py"),
    ("logout revoke session", "auth/login.py"),
    ("timeline ranking is slow", "feed/timeline.ts"),
    ("push notifications missing stale tokens", "notifications/push.py"),
    ("dark mode oled night setting", "settings/theme.ts"),
    ("retry failed stripe webhook deliveries", "payments/webhooks.py"),
    ("users table migration email unique", "infra/schema.sql"),
    ("password reset email token", "auth/password.py"),
    ("order total discount tax calculation", "orders/pricing.py"),
    ("search products catalog prefix", "catalog/search.ts"),
    ("rate limiting token bucket api", "middleware/ratelimit.py"),
    ("health check deploy version endpoint", "health.py"),
    ("csv export feedback rows", "exports/csv.py"),
    ("cache invalidation redis pattern", "cache/store.py"),
    ("chargeback dispute evidence", "payments/disputes.py"),
]


def run_eval(root: str, tenant: str = "t-eval", top_k: int = 3) -> dict:
    sync_repo(root, tenant, FIX, alias="demo")
    results = []
    for query, expected in QUERIES:
        hits = search_index(root, tenant, query, top_k=top_k)
        paths = [h["path"] for h in hits]
        passed = any(expected in p for p in paths)
        results.append({"query": query, "expected": expected,
                        "got": paths, "pass": passed})
    passed = sum(1 for r in results if r["pass"])
    return {"passed": passed, "total": len(results), "results": results}


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-pass", type=int, default=16)
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        report = run_eval(tmp)
    print(f"EVAL code-search: {report['passed']}/{report['total']} (bar: {args.min_pass})")
    for r in report["results"]:
        mark = "PASS" if r["pass"] else "FAIL"
        print(f"  [{mark}] {r['query']!r} -> {r['got'][0] if r['got'] else 'no hits'}")
    if report["passed"] < args.min_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
