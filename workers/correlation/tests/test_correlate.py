import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from correlation import detect_spike, find_suspects  # noqa: E402

SPIKE = "2026-09-05T12:00:00Z"


def _dep(service, at, version="1.4.3", sha="ab12"):
    return {"id": f"d-{version}", "service": service, "version": version,
            "commit_sha": sha, "env": "production", "deployed_at": at}


def test_spike_after_deploy_names_suspect():
    deploys = [
        _dep("payments-api", "2026-09-05T10:00:00Z"),
        _dep("payments-api", "2026-09-04T08:00:00Z", version="1.4.2", sha="99ff"),
    ]
    suspects = find_suspects(deploys, SPIKE, "payments-api")
    assert len(suspects) == 1, suspects
    assert suspects[0]["deployment"]["version"] == "1.4.3"
    assert suspects[0]["deployment"]["commit_sha"] == "ab12"
    assert 0.5 < suspects[0]["score"] <= 1.0


def test_no_deploy_in_window_returns_empty():
    deploys = [_dep("payments-api", "2026-09-01T08:00:00Z", version="1.4.0")]
    assert find_suspects(deploys, SPIKE, "payments-api") == []


def test_other_services_and_future_deploys_ignored():
    deploys = [
        _dep("search-api", "2026-09-05T11:00:00Z"),
        _dep("payments-api", "2026-09-05T13:00:00Z", version="1.4.4"),
    ]
    assert find_suspects(deploys, SPIKE, "payments-api") == []


def test_closest_deploy_ranks_first():
    deploys = [
        _dep("payments-api", "2026-09-05T07:00:00Z", version="1.4.2", sha="aa"),
        _dep("payments-api", "2026-09-05T11:30:00Z", version="1.4.3", sha="bb"),
    ]
    suspects = find_suspects(deploys, SPIKE, "payments-api")
    assert [s["deployment"]["version"] for s in suspects] == ["1.4.3", "1.4.2"]


def test_detect_spike_finds_jump():
    assert detect_spike([4, 5, 6, 5, 60, 70]) == 4


def test_detect_spike_quiet_series_is_none():
    assert detect_spike([4, 5, 6, 5, 6, 5]) is None
    assert detect_spike([0, 0, 1, 0]) is None  # no baseline
