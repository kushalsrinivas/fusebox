"""Investigation evals: 15 seeded scenarios over the deterministic runner.

Metrics (Phase 3 exit bars):
- root-cause top-1 >= 60% (9/15): top hypothesis names the right deploy,
  or correctly returns needs_info / deploy-less verdict.
- citation precision >= 90%: every cited ref must come from the evidence given.

Run: `python evals/run_investigation_evals.py [--min-top1 9 --min-prec 0.9]`
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.runner import investigate  # noqa: E402

SVC = "payments-api"


def _dep(i, service=SVC, version="1.4.3", sha="ab12", at="2026-09-05T10:00:00Z"):
    return {"deployment": {"id": i, "service": service, "version": version,
                           "commit_sha": sha, "env": "production", "deployed_at": at},
            "score": 0.8, "reason": "deployed 120m before spike (window 6h)"}


def _err(fp="fp1", service=SVC, title="capture failed: timeout", count=42):
    return {"fingerprint": fp, "service": service, "title": title, "count": count}


def _code(path="apps/payments/checkout.py", symbol="charge"):
    return {"path": path, "symbol": symbol,
            "ref": f"index://demo/{path}#L7-L14"}


def _members(n=3):
    return [{"id": f"f{i}", "title": "checkout crash when tapping pay"} for i in range(n)]


def SCENARIOS():
    d1 = _dep("dep_891")
    return [
        # (name, kwargs, expected_top_deploy_id or None, needs_info?)
        ("classic crash after deploy",
         dict(title="checkout crash when tapping pay", count=42, members=_members(),
              error_groups=[_err()], suspects=[d1], code_hits=[_code()], service=SVC), "dep_891", False),
        ("closer deploy wins (correlate ranks first)",
         dict(title="checkout crash", count=10, members=_members(2),
              error_groups=[_err()], code_hits=[_code()], service=SVC,
              suspects=[d1, _dep("dep_old", version="1.4.2", sha="aa",
                                 at="2026-09-05T07:00:00Z")]), "dep_891", False),
        ("spike, no deploy in window",
         dict(title="checkout crash", count=8, members=_members(2),
              error_groups=[_err()], suspects=[], code_hits=[_code()], service=SVC), None, False),
        ("no evidence at all",
         dict(title="weird glitch", count=1, members=_members(1),
              error_groups=[], suspects=[], code_hits=[], service=SVC), None, True),
        ("other-service deploys only",
         dict(title="checkout crash", count=5, members=_members(2),
              error_groups=[], suspects=[], code_hits=[], service=SVC), None, True),
        ("feature request, no telemetry",
         dict(title="dark mode please", count=12, members=_members(2),
              error_groups=[], suspects=[], code_hits=[], service=None), None, True),
        ("login 500 with suspect",
         dict(title="login fails with 500", count=20, members=_members(4),
              error_groups=[_err("fp9", title="POST /login 500", count=20)],
              suspects=[_dep("dep_900", version="2.1.0", sha="cc34")],
              code_hits=[_code("apps/auth/login.py", "login")], service=SVC), "dep_900", False),
        ("no code hits, still hypothesizes",
         dict(title="checkout crash", count=15, members=_members(3),
              error_groups=[_err()], suspects=[d1], code_hits=[], service=SVC), "dep_891", False),
        ("no errors, code + deploy",
         dict(title="checkout crash", count=6, members=_members(2),
              error_groups=[], suspects=[d1], code_hits=[_code()], service=SVC), "dep_891", False),
        ("multiple error groups cite top",
         dict(title="checkout crash", count=30, members=_members(5),
              error_groups=[_err(), _err("fp2", title="minor warn", count=2)],
              suspects=[d1], code_hits=[_code()], service=SVC), "dep_891", False),
        ("future deploy already excluded",
         dict(title="feed slow", count=7, members=_members(2),
              error_groups=[_err("fp3", title="timeline p99 8s", count=7)],
              suspects=[], code_hits=[_code("apps/feed/timeline.ts", "rankFeed")],
              service=SVC), None, False),
        ("high-volume burst severity 5",
         dict(title="checkout crash payment down", count=120, members=_members(10),
              error_groups=[_err()], suspects=[d1], code_hits=[_code()], service=SVC), "dep_891", False),
        ("empty title edge",
         dict(title="", count=2, members=_members(1),
              error_groups=[_err()], suspects=[d1], code_hits=[_code()], service=SVC), "dep_891", False),
        ("other-service errors do not leak",
         dict(title="checkout crash", count=9, members=_members(2),
              error_groups=[_err("fpX", service="search-api", title="search 500", count=99),
                            _err()],
              suspects=[d1], code_hits=[_code()], service=SVC), "dep_891", False),
        ("single report with full evidence",
         dict(title="capture timeout on pay", count=1, members=_members(1),
              error_groups=[_err()], suspects=[d1], code_hits=[_code()], service=SVC), "dep_891", False),
    ]


def run_evals():
    top1, cited, valid = 0, 0, 0
    details = []
    for name, kw, expected, needs_info in SCENARIOS():
        res = investigate(cluster_key="c_test", **kw)
        known = {h["ref"] for h in kw["code_hits"]}
        known |= {f"pil://deployments/{s['deployment']['id']}" for s in kw["suspects"]}
        known |= {f"pil://errors/{g['fingerprint']}" for g in kw["error_groups"]}
        hyps = res["hypotheses"]
        if needs_info:
            ok = res["status"] == "needs_info" and not hyps
        elif expected is None:
            ok = bool(hyps) and hyps[0].get("deployment") is None
        else:
            ok = bool(hyps) and (hyps[0].get("deployment") or {}).get("id") == expected
        top1 += ok
        for h in hyps:
            for c in h["citations"]:
                cited += 1
                valid += c in known
        details.append({"scenario": name, "top1": ok, "status": res["status"],
                        "confidence": res["confidence"]})
    return {"top1": top1, "total": len(SCENARIOS()),
            "precision": (valid / cited) if cited else 1.0,
            "details": details}


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-top1", type=int, default=9)
    ap.add_argument("--min-prec", type=float, default=0.9)
    args = ap.parse_args()
    rep = run_evals()
    print(f"EVAL investigations: top1 {rep['top1']}/{rep['total']} (bar {args.min_top1}), "
          f"citation precision {rep['precision']:.3f} (bar {args.min_prec})")
    for d in rep["details"]:
        print(f"  [{'PASS' if d['top1'] else 'FAIL'}] {d['scenario']} -> "
              f"{d['status']} conf={d['confidence']}")
    if rep["top1"] < args.min_top1 or rep["precision"] < args.min_prec:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
