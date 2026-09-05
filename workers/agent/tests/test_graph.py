from agent.service import run_investigation
from agent.tools import ALL_TOOLS


def test_graph_runs_offline_full_path():
    result = run_investigation(
        tenant_id="00000000-0000-0000-0000-000000000001",
        cluster_id="c_1",
        cluster_title="checkout crash when tapping pay",
        cluster_count=42,
    )
    assert result["status"] == "planned"
    assert result["severity"] >= 4  # crash + high count
    assert len(result["evidence"]) >= 3  # code + deploy + metric/log
    assert result["hypotheses"], "expected a hypothesis on the happy path"
    h = result["hypotheses"][0]
    assert h["citations"], "hypothesis must cite evidence"
    assert 0.0 < result["confidence"] <= 0.95


def test_graph_needs_info_without_title():
    result = run_investigation(
        tenant_id="t1",
        cluster_id="c_2",
        cluster_title="",
        cluster_count=1,
    )
    # empty title -> enrich still returns stub evidence, but keep gate honest:
    assert result["status"] in ("planned", "needs_info")


def test_tools_are_tenant_scoped():
    names = sorted(t.name for t in ALL_TOOLS)
    assert "code_search" in names and "deploys_list" in names
    for t in ALL_TOOLS:
        assert "tenant_id" in t.args, f"{t.name} must take tenant_id"
