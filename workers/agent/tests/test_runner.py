import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.runner import investigate, severity_of  # noqa: E402
from evals.run_investigation_evals import run_evals  # noqa: E402


def test_investigation_evals_meet_bars():
    rep = run_evals()
    assert rep["top1"] >= 9, [d for d in rep["details"] if not d["top1"]]
    assert rep["precision"] >= 0.9


def test_severity_math():
    assert severity_of("checkout crash payment down", 120) == 5
    assert severity_of("dark mode please", 3) == 2


def test_needs_info_when_empty():
    res = investigate("c1", "mystery", 1, [], [], [], [], service="svc")
    assert res["status"] == "needs_info" and res["hypotheses"] == []
