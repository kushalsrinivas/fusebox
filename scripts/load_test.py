"""Load test: N tenants x M feedback posts + reads against a running gateway.

Usage: make api  # in one shell
       python scripts/load_test.py --tenants 5 --events 40 --base http://localhost:8000
Stdlib only (urllib + threads). Prints p50/p95 latency + accepted counts.
"""

import argparse
import json
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def post(base, key, path, payload=None, method="GET"):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json",
                                          "X-API-Key": key})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
        return time.time() - t0, r.status, body
    except Exception as e:  # noqa: BLE001
        return time.time() - t0, -1, str(e).encode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--tenants", type=int, default=5)
    ap.add_argument("--events", type=int, default=40)
    ap.add_argument("--key", default="dev-key")
    args = ap.parse_args()

    lat, ok, fail = [], 0, 0
    def one(i):
        nonlocal ok, fail
        t, s, _ = post(args.base, args.key, "/v1/feedback",
                       {"title": f"load event {i}", "body": "synthetic"}, "POST")
        lat.append(t)
        if s == 202:
            ok += 1
        else:
            fail += 1
    with ThreadPoolExecutor(max_workers=16) as ex:
        list(ex.map(one, range(args.tenants * args.events)))
    lat.sort()
    p50 = lat[len(lat) // 2] if lat else 0
    p95 = lat[int(len(lat) * 0.95)] if lat else 0
    print(f"tenants={args.tenants} events={args.tenants * args.events} "
          f"accepted={ok} failed={fail} p50={p50:.3f}s p95={p95:.3f}s")


if __name__ == "__main__":
    main()
