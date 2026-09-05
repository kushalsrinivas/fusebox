import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pil_indexer.store import search_index  # noqa: E402
from pil_indexer.sync import list_repos, sync_repo  # noqa: E402

FIX = str(Path(__file__).parent / "fixtures" / "demo-repo")
TENANT = "t-eval"


def test_sync_then_search_grounded(tmp_path):
    root = str(tmp_path)
    stats = sync_repo(root, TENANT, FIX, alias="demo")
    assert stats["files"] >= 10, stats
    assert stats["chunks"] >= 20, stats

    repos = list_repos(root, TENANT)
    assert [r["repo"] for r in repos] == ["demo"]

    hits = search_index(root, TENANT, "checkout charge capture", top_k=3)
    assert hits, "expected hits"
    assert any("checkout.py" in h["path"] for h in hits), [h["path"] for h in hits]
    assert all(h["ref"].startswith("index://demo/") for h in hits)


def test_incremental_second_sync_is_clean(tmp_path):
    root = str(tmp_path)
    first = sync_repo(root, TENANT, FIX, alias="demo")
    second = sync_repo(root, TENANT, FIX, alias="demo")
    assert second["changed"] == 0
    assert second["chunks"] == first["chunks"]
    assert second["files"] == first["files"]


def test_edit_reindexes_only_changed_file(tmp_path):
    import shutil

    work = tmp_path / "repo"
    shutil.copytree(FIX, work)
    root = str(tmp_path / "idx")
    sync_repo(root, TENANT, str(work), alias="demo")
    (work / "apps" / "health.py").write_text((work / "apps" / "health.py").read_text() + "\n# bump\n")
    second = sync_repo(root, TENANT, str(work), alias="demo")
    assert second["changed"] == 1, second


def test_tenant_isolation(tmp_path):
    root = str(tmp_path)
    sync_repo(root, "tenant-a", FIX, alias="demo")
    assert search_index(root, "tenant-b", "checkout charge") == []
