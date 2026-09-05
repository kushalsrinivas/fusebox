import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from graph import Graph, build_graph, timeline  # noqa: E402


def _rows():
    clusters = [{"key": "c_1", "title": "checkout crash when tapping pay",
                 "count": 3, "service_hint": "payments-api",
                 "members": ["f1", "f2", "f3"]}]
    feedback = [{"id": "f1", "title": "checkout crash when tapping pay"},
                {"id": "f2", "title": "checkout crash on tap pay"},
                {"id": "f9", "title": "dark mode please"}]
    errors = [{"fingerprint": "fp1", "service": "payments-api",
               "title": "capture failed: timeout", "count": 42}]
    deploys = [{"id": "dep_891", "service": "payments-api", "version": "1.4.3",
                "commit_sha": "ab12", "deployed_at": "2026-09-05T10:00:00Z"}]
    code = [{"repo": "demo", "path": "apps/payments/checkout.py", "symbol": "charge",
             "ref": "index://demo/apps/payments/checkout.py#L7-L14",
             "service": "payments-api"}]
    return clusters, feedback, errors, deploys, code


def test_build_links_cluster_to_evidence():
    g = build_graph(*_rows())
    assert "cluster:c_1" in g.nodes
    kinds = {(e["kind"]) for e in g.edges}
    assert {"IN_CLUSTER", "AFFECTS_SERVICE", "EMITTED_BY", "DEPLOYED_AS"} <= kinds
    # unrelated feedback stays unlinked
    assert not [e for e in g.edges if "f9" in e["src"]]


def test_timeline_orders_report_error_deploy_code():
    g = build_graph(*_rows())
    tl = timeline(g, "c_1")
    kinds = [e["kind"] for e in tl]
    assert kinds == sorted(kinds, key=lambda k: {"report": 0, "error": 1, "deploy": 2,
                                                 "code": 3, "hypothesis": 4}[k])
    assert any(e["kind"] == "error" for e in tl)
    assert any("ab12" in e["excerpt"] for e in tl if e["kind"] == "deploy")


def test_hypothesis_edges_never_overwrite_deterministic():
    g = build_graph(*_rows())
    n_before = len(g.edges)
    g.hypothesize("cluster:c_1", "deployment:dep_891", 0.9, "spike aligns with deploy")
    assert len(g.edges) == n_before + 1
    edge = g.edges[-1]
    assert edge["created_by"] == "agent" and edge["confidence"] == 0.9
    assert any(e["kind"] == "DEPLOYED_AS" for e in g.edges)


def test_save_load_roundtrip(tmp_path):
    g = build_graph(*_rows())
    g.save(str(tmp_path), "t1")
    g2 = Graph.load(str(tmp_path), "t1")
    assert g2.nodes == g.nodes and g2.edges == g.edges
    assert Graph.load(str(tmp_path), "missing").nodes == {}
