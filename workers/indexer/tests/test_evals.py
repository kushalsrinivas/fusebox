import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.run_evals import run_eval  # noqa: E402


def test_code_search_evals_meet_bar():
    with tempfile.TemporaryDirectory() as tmp:
        report = run_eval(tmp)
    failures = [r for r in report["results"] if not r["pass"]]
    assert report["passed"] >= 16, f"only {report['passed']}/20; failures: {failures}"
