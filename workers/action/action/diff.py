"""Minimal unified-diff parse/validate/apply (stdlib only).

Supports the subset Coder emits: `--- a/path` / `+++ b/path` headers,
`@@ -start[,len] +start[,len] @@` hunks, context/added/removed lines.
New files (`--- /dev/null`), deletions (`+++ /dev/null`) supported.
"""

from __future__ import annotations

import re

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

MAX_LINES_DEFAULT = 500
DENYLIST = ("migrations/", "infra/", "auth/", ".env", "id_rsa", ".pem")


def parse_diff(text: str) -> list[dict]:
    files: list[dict] = []
    cur: dict | None = None
    for raw in text.splitlines():
        if raw.startswith("--- "):
            old = raw[4:].strip()
            cur = {"old": None if old == "/dev/null" else _strip(old), "new": None,
                   "hunks": []}
            files.append(cur)
        elif raw.startswith("+++ ") and cur is not None:
            new = raw[4:].strip()
            cur["new"] = None if new == "/dev/null" else _strip(new)
        elif raw.startswith("@@") and cur is not None:
            m = HUNK.match(raw)
            if not m:
                raise ValueError(f"bad hunk header: {raw}")
            cur["hunks"].append({"old_start": int(m.group(1)),
                                 "old_len": int(m.group(2) or 1),
                                 "new_start": int(m.group(3)),
                                 "new_len": int(m.group(4) or 1),
                                 "lines": []})
        elif cur is not None and cur["hunks"]:
            if raw[:1] in (" ", "+", "-", "\\"):
                if not raw.startswith("\\"):
                    cur["hunks"][-1]["lines"].append(raw)
            else:
                raise ValueError(f"unexpected diff line: {raw!r}")
    return [f for f in files if f["new"] is not None or f["old"] is not None]


def _strip(p: str) -> str:
    return p[2:] if p.startswith(("a/", "b/")) else p


def _denied(path: str, denylist: tuple[str, ...]) -> str | None:
    """Match denylist entries as path components or filename suffixes.

    Catches apps/auth/login.py (component) as well as auth/login.py (prefix)
    and keys like id_rsa / *.pem (suffix).
    """
    parts = path.split("/")
    for d in denylist:
        seg = d.rstrip("/")
        if "/" in seg:
            if path == seg or path.startswith(seg + "/"):
                return d
        elif seg in parts or path.endswith(seg):
            return d
    return None


def changed_paths(files: list[dict]) -> list[str]:
    return [f["new"] or f["old"] for f in files]  # type: ignore[misc]


def diff_size(text: str) -> int:
    return sum(1 for l in text.splitlines()
               if l[:1] in ("+", "-") and not l.startswith(("+++", "---")))


def validate_diff(text: str, max_lines: int = MAX_LINES_DEFAULT,
                  denylist: tuple[str, ...] = DENYLIST) -> list[str]:
    """Return blocking issues (empty = ok to proceed)."""
    issues = []
    if diff_size(text) > max_lines:
        issues.append(f"diff too large: {diff_size(text)} > {max_lines} lines")
    try:
        files = parse_diff(text)
    except ValueError as e:
        return [f"unparseable diff: {e}"]
    if not files:
        issues.append("diff touches no files")
    seen = []
    for f in files:
        for p in (f["old"], f["new"]):
            if p and p not in seen:
                seen.append(p)
    for p in seen:
        if p.startswith("/") or ".." in p.split("/"):
            issues.append(f"unsafe path: {p}")
        hit = _denied(p, denylist)
        if hit:
            issues.append(f"denylisted path (needs explicit approval): {p} [{hit}]")
    return issues


def apply_diff(base: dict[str, str], text: str) -> dict[str, str]:
    """Apply unified diff to {path: content} mapping. Returns new mapping."""
    out = dict(base)
    for f in parse_diff(text):
        old, new = f["old"], f["new"]
        if old is None and new is not None:  # new file
            content: list[str] = []
            for h in f["hunks"]:
                content.extend(l[1:] for l in h["lines"] if l.startswith("+"))
            out[new] = "\n".join(content) + ("\n" if content else "")
        elif new is None and old is not None:  # deletion
            out.pop(old, None)
        else:
            assert old is not None and new is not None
            src = base.get(old, "").splitlines()
            dst: list[str] = []
            pos = 0
            for h in f["hunks"]:
                start = h["old_start"] - 1
                dst.extend(src[pos:start])
                pos = start
                for l in h["lines"]:
                    if l.startswith(" "):
                        dst.append(l[1:])
                        pos += 1
                    elif l.startswith("-"):
                        pos += 1
                    elif l.startswith("+"):
                        dst.append(l[1:])
            dst.extend(src[pos:])
            out[new] = "\n".join(dst) + ("\n" if dst else "")
            if new != old:
                out.pop(old, None)
    return out
