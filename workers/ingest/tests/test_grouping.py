from ingest.grouping import group_feedback


def _fb(i, title, body="", hint=None):
    return {"id": f"f{i}", "title": title, "body": body, "service_hint": hint}


def test_checkout_burst_groups_together():
    items = [
        _fb(1, "checkout crash when tapping pay", "app closes on pay", "payments-api"),
        _fb(2, "checkout crash on tap pay button", "closes every time", "payments-api"),
        _fb(3, "checkout crash tapping pay", "ios 17 pay crash", "payments-api"),
        _fb(4, "dark mode please", "oled night mode", None),
    ]
    clusters = group_feedback(items)
    by_member = {}
    for c in clusters:
        for m in c["members"]:
            by_member[m] = c["key"]
    assert by_member["f1"] == by_member["f2"] == by_member["f3"]
    assert by_member["f4"] != by_member["f1"]
    big = next(c for c in clusters if c["key"] == by_member["f1"])
    assert big["count"] == 3
    assert big["service_hint"] == "payments-api"


def test_singletons_stay_single():
    items = [_fb(1, "checkout crash pay"), _fb(2, "dark mode please"),
             _fb(3, "export csv broken")]
    clusters = group_feedback(items)
    assert len(clusters) == 3
    assert all(c["count"] == 1 for c in clusters)
