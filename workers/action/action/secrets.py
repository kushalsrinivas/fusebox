"""Secret scan over proposed diffs. Blocks before any external write."""

import re

PATTERNS = {
    "api token": re.compile(r"\b(sk-[A-Za-z0-9\-_]{8,}|ghp_[A-Za-z0-9]{8,}|xox[bap]-[A-Za-z0-9\-_]+|AIza[A-Za-z0-9\-_]{20,})\b"),
    "private key": re.compile(r"-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    "password assignment": re.compile(r"(?i)(password|passwd|secret)\s*=\s*['\"][^'\"]{4,}['\"]"),
}


def scan_diff(text: str) -> list[dict]:
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:]
        for kind, pat in PATTERNS.items():
            if pat.search(body):
                hits.append({"kind": kind, "line": i,
                             "excerpt": body[:80]})
    return hits
