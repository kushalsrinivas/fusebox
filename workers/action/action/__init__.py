"""Fix pipeline building blocks (pure + stdlib, except pr.py httpx).

diff.py     parse/validate/apply unified diffs (no `patch` binary needed)
secrets.py  token/secret scan over diffs (blocks before any external write)
sandbox.py  apply diff to a temp copy, byte-compile, run checks with timeout
risk.py     regression-risk score from blast radius + sensitivity + size
pr.py       draft-PR body builder + GitHub draft-PR creator (or dry-run)
"""

from .diff import apply_diff, changed_paths, diff_size, parse_diff, validate_diff
from .risk import score_risk
from .sandbox import run_checks
from .secrets import scan_diff

__all__ = [
    "apply_diff", "changed_paths", "diff_size", "parse_diff", "validate_diff",
    "score_risk", "run_checks", "scan_diff",
]
