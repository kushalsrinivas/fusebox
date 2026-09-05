import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.run_action_evals import run_evals  # noqa: E402


def test_action_evals_meet_bar():
    rep = run_evals()
    assert rep["passed"] >= 8, [r for r in rep["results"] if not r["pass"]]
