from verify import overall, verify_fix


def test_fixed_when_errors_stop():
    r = verify_fix(before=40, after=0, elapsed_h=25)
    assert r["verdict"] == "verified_fixed"


def test_fixed_on_big_drop():
    assert verify_fix(100, 5, 30)["verdict"] == "verified_fixed"


def test_regressed_on_growth():
    r = verify_fix(10, 20, 25)
    assert r["verdict"] == "regressed" and r["delta"] == 1.0


def test_too_early_is_inconclusive():
    r = verify_fix(40, 0, elapsed_h=2)
    assert r["verdict"] == "inconclusive" and r["delta"] is None


def test_no_baseline_is_inconclusive():
    assert verify_fix(0, 0, 30)["verdict"] == "inconclusive"


def test_middle_is_inconclusive():
    assert verify_fix(100, 60, 30)["verdict"] == "inconclusive"


def test_overall_worst_wins():
    assert overall([{"verdict": "verified_fixed"},
                    {"verdict": "regressed"}])["status"] == "regressed"
    assert overall([{"verdict": "verified_fixed"}])["status"] == "verified_fixed"
    assert overall([])["status"] == "inconclusive"
