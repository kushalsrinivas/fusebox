import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pil_indexer.sync import sync_repo  # noqa: E402

FIX = str(Path(__file__).parent / "fixtures" / "demo-repo")


def test_pilignore_excludes_dirs_and_globs(tmp_path):
    work = tmp_path / "repo"
    shutil.copytree(FIX, work)
    (work / "archive").mkdir()
    (work / "archive" / "old.py").write_text("def old():\n    return 0\n")
    (work / "apps" / "notes.log").write_text("x")
    (work / "apps" / "debug.log").write_text("y")
    (work / ".pilignore").write_text("# skip vendored history\narchive/\n*.log\n")
    stats = sync_repo(str(tmp_path / "idx"), "t1", str(work), alias="demo")
    from pil_indexer.store import load
    paths = {c["path"] for c in load(str(tmp_path / "idx"), "t1")}
    assert "archive/old.py" not in paths
    assert not any(p.endswith(".log") for p in paths)
    assert "apps/health.py" in paths
