from action.diff import apply_diff, changed_paths, diff_size, parse_diff, validate_diff

GOOD = """--- a/apps/payments/checkout.py
+++ b/apps/payments/checkout.py
@@ -1,3 +1,4 @@
 def charge(order_id):
-    receipt = _gateway.capture(auth["auth_id"])
+    receipt = _gateway.capture(auth["auth_id"], timeout_ms=5000)
     return receipt
+    # retry once on timeout
"""

BASE = {"apps/payments/checkout.py": 'def charge(order_id):\n    receipt = _gateway.capture(auth["auth_id"])\n    return receipt\n'}


def test_parse_and_apply():
    files = parse_diff(GOOD)
    assert changed_paths(files) == ["apps/payments/checkout.py"]
    out = apply_diff(BASE, GOOD)
    assert "timeout_ms=5000" in out["apps/payments/checkout.py"]
    assert "return receipt" in out["apps/payments/checkout.py"]


def test_clean_diff_validates():
    assert validate_diff(GOOD) == []


def test_denylist_blocked():
    bad = GOOD.replace("apps/payments/checkout.py", "infra/deploy.yaml")
    issues = validate_diff(bad)
    assert any("denylisted" in i for i in issues), issues


def test_unsafe_path_blocked():
    bad = GOOD.replace("a/apps/payments/checkout.py", "a/../../etc/passwd")
    assert any("unsafe" in i for i in validate_diff(bad))


def test_oversize_blocked():
    big = GOOD + "".join(f"+line{i}\n" for i in range(600))
    assert any("too large" in i for i in validate_diff(big, max_lines=500))


def test_diff_size_counts():
    assert diff_size(GOOD) == 3
