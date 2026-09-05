"""Sandbox: apply a diff to a temp copy and run checks with a timeout.

Local-first substitute for Firecracker (arch §4.9): no network isolation yet
(documented), but full audit trail + timeouts + temp-dir containment.
Default check byte-compiles every touched Python file; callers add repo
checks (pytest subset, tsc) explicitly.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .diff import apply_diff, changed_paths, parse_diff

DEFAULT_TIMEOUT_S = 600


def run_checks(base_files: dict[str, str], diff: str,
               extra_checks: list[list[str]] | None = None,
               timeout_s: int = DEFAULT_TIMEOUT_S) -> dict:
    """Returns {ok, applied:[paths], logs:[...], checks:[{cmd, rc, out}]}."""
    logs: list[str] = []
    try:
        files = parse_diff(diff)
    except ValueError as e:
        return {"ok": False, "applied": [], "logs": [f"unparseable diff: {e}"], "checks": []}
    paths = changed_paths(files)
    tmp = Path(tempfile.mkdtemp(prefix="pil-sandbox-"))
    try:
        merged = apply_diff(base_files, diff)
        for p in paths:
            if p in merged:
                dest = tmp / p
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(merged[p])
        logs.append(f"applied {len(paths)} file(s) to {tmp}")

        results = []
        py_files = [p for p in paths if p.endswith(".py") and (tmp / p).exists()]
        if py_files:
            r = _run(["python3", "-m", "py_compile", *py_files], tmp, timeout_s)
            results.append(r)
            logs.append(f"py_compile: rc={r['rc']}")
        for cmd in extra_checks or []:
            r = _run(cmd, tmp, timeout_s)
            results.append(r)
            logs.append(f"{' '.join(cmd)}: rc={r['rc']}")
        ok = all(r["rc"] == 0 for r in results)
        return {"ok": ok, "applied": paths, "logs": logs, "checks": results}
    except subprocess.TimeoutExpired as e:
        return {"ok": False, "applied": paths,
                "logs": logs + [f"TIMEOUT after {timeout_s}s: {e.cmd}"], "checks": []}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run(cmd: list[str], cwd: Path, timeout_s: int) -> dict:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout_s)
        out = (p.stdout + p.stderr)[-4000:]
        return {"cmd": cmd, "rc": p.returncode, "out": out}
    except FileNotFoundError:
        return {"cmd": cmd, "rc": 127, "out": f"not found: {cmd[0]}"}
