from agent.analyst import render_proposals


def test_render_proposals_structure():
    digest = [{"cluster_key": "c_0", "title": "dark mode please", "requests": 3,
               "feature_ratio": 0.67, "service_hint": None,
               "sample_titles": ["dark mode", "oled mode"]}]
    props = render_proposals(digest)
    assert len(props) == 1
    assert props[0]["markdown"].startswith("## Proposal: dark mode please")
    assert "- dark mode" in props[0]["markdown"]
    assert "3 request(s)" in props[0]["problem"]
