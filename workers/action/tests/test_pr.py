from action.pr import build_pr_body, open_draft_pr


class FakeGitHub:
    def __init__(self):
        self.calls = []

    def get_ref(self, repo, ref):
        self.calls.append(("get_ref", ref))
        return "base-sha"

    def create_ref(self, repo, ref, sha):
        self.calls.append(("create_ref", ref))

    def create_blob(self, repo, content):
        self.calls.append(("create_blob", len(content)))
        return f"blob-{len(content)}"

    def create_tree(self, repo, base, blobs):
        self.calls.append(("create_tree", len(blobs)))
        return "tree-sha"

    def create_commit(self, repo, msg, tree, parents):
        self.calls.append(("create_commit", msg))
        return "commit-sha"

    def update_ref(self, repo, ref, sha):
        self.calls.append(("update_ref", ref))

    def create_pr(self, repo, title, head, base, body, draft):
        self.calls.append(("create_pr", draft))
        assert draft is True
        return {"html_url": "https://github.com/o/r/pull/1", "number": 1}


def test_body_contains_evidence_risk_sandbox():
    body = build_pr_body(
        "checkout crash", {"title": "h", "reason": "r", "citations": ["index://x#L1"]},
        {"level": "medium", "score": 0.5, "factors": ["wide"]},
        {"logs": ["py_compile: rc=0"]}, "demo")
    assert body.startswith("[Fusebox]") and "index://x#L1" in body and "0.5" in body


def test_dry_run_returns_artifact():
    out = open_draft_pr("o/r", "fuse/c-1-ab12", {"a.py": "x"}, "title\n\nbody", None)
    assert out["dry_run"] and out["files"] == ["a.py"] and out["branch"] == "fuse/c-1-ab12"


def test_live_path_uses_api_sequence():
    fake = FakeGitHub()
    out = open_draft_pr("o/r", "fuse/x", {"a.py": "print(1)"}, "T\n\nB", "tok", _api=fake)
    assert out["pr_url"].endswith("/pull/1") and not out["dry_run"]
    assert [c[0] for c in fake.calls] == ["get_ref", "create_ref", "create_blob",
                                          "create_tree", "create_commit", "update_ref",
                                          "create_pr"]
