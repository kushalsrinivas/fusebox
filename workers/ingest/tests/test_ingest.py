from ingest.cluster import should_merge, similarity
from ingest.normalize import normalize
from ingest.redact import redact


def test_redact_email_token():
    s = redact("mail me at a@x.com or use sk-abc123XYZ456")
    assert "a@x.com" not in s and "sk-abc" not in s
    assert "[REDACTED_EMAIL]" in s and "[REDACTED_TOKEN]" in s


def test_normalize_defaults():
    e = normalize({"title": "crash"}, "t1", "api")
    assert e["tenant_id"] == "t1" and e["type"] == "other"
    assert e["title"] == "crash"


def test_similarity_merge():
    a = "checkout crash when tapping pay"
    b = "checkout crash when tapping pay button"
    assert similarity(a, b) > 0.55
    assert should_merge(a, b) == "auto"
    assert should_merge("checkout crash", "dark mode please") == "new"
