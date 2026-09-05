import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from insights import build_digest  # noqa: E402


def test_digest_ranks_feature_clusters():
    clusters = [
        {"key": "c_0", "title": "dark mode please", "service_hint": None,
         "members": ["f1", "f2", "f3"]},
        {"key": "c_1", "title": "checkout crash", "service_hint": "payments-api",
         "members": ["f4", "f5"]},
    ]
    fb = {"f1": {"title": "dark mode", "type": "feature_request"},
          "f2": {"title": "oled mode", "type": "feature_request"},
          "f3": {"title": "night theme", "type": "other"},
          "f4": {"title": "crash", "type": "bug"},
          "f5": {"title": "crash again", "type": "bug"}}
    digest = build_digest(clusters, fb)
    assert len(digest) == 1
    assert digest[0]["cluster_key"] == "c_0"
    assert digest[0]["requests"] == 3
    assert digest[0]["feature_ratio"] == round(2 / 3, 2)


def test_empty_members_skipped():
    assert build_digest([{"key": "c", "members": []}], {}) == []
