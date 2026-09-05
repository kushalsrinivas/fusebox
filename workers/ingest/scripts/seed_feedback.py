"""Seed demo tenant with synthetic feedback via the running API (fallback: print curl)."""

import argparse
import json
import random
import urllib.request

TITLES = [
    ("checkout crash when tapping pay", "taps pay, app closes on iOS 17", "crash"),
    ("login fails with 500", "correct password still 500s", "bug"),
    ("feed is slow", "timeline takes 8s to load", "bug"),
    ("dark mode please", "oled dark mode for night use", "feature_request"),
    ("push notifications missing", "no push after update 1.4.2", "bug"),
]

API = "http://localhost:8000/v1/feedback"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--key", default="dev-key")
    args = ap.parse_args()
    ok = 0
    for i in range(args.count):
        t, b, ty = random.choice(TITLES)
        payload = json.dumps(
            {"title": f"{t} #{i}", "body": b, "type": ty, "app_version": "1.4.2"}
        ).encode()
        req = urllib.request.Request(
            API, data=payload,
            headers={"Content-Type": "application/json", "X-API-Key": args.key},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                if r.status == 202:
                    ok += 1
        except Exception as e:
            print(f"seed {i} failed (is the api running?): {e}")
            break
    print(f"seeded {ok}/{args.count}")


if __name__ == "__main__":
    main()
