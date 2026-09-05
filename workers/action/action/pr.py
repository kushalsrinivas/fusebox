"""Draft-PR body builder + GitHub draft-PR creator (or dry-run artifact).

Real path uses the GitHub REST API with a tenant installation token
(PIL_GITHUB_TOKEN): HEAD sha -> branch ref -> blobs -> tree -> commit ->
draft PR. Dry-run (no token) returns the exact body + file list so the
human review UI shows what WOULD be opened.
"""

from __future__ import annotations

import base64


def build_pr_body(cluster_title: str, hypothesis: dict, risk: dict,
                  sandbox: dict, repo: str) -> str:
    h = hypothesis or {}
    lines = [
        f"[Fusebox] {cluster_title}: {h.get('title', 'proposed fix')}",
        "",
        "## Root cause",
        h.get("reason", "see linked investigation"),
        "",
        "## Evidence",
        *[f"- `{c}`" for c in h.get("citations", [])],
        "",
        f"## Regression risk: {risk.get('level')} ({risk.get('score')})",
        *[f"- {f}" for f in risk.get("factors", [])],
        "",
        "## Sandbox",
        *[f"- {l}" for l in sandbox.get("logs", [])],
        "",
        f"Source repo snapshot: `{repo}`. Human merge required — Fusebox never pushes to main.",
    ]
    return "\n".join(lines)


def open_draft_pr(repo: str, branch: str, files: dict[str, str], body: str,
                  token: str | None, base: str = "main",
                  _api=None) -> dict:
    """Open a draft PR. Dry-run when token is None.

    repo: "owner/name". files: {path: content} full new contents.
    _api: injectable minimal GitHub client (tests); defaults to httpx impl.
    """
    title = body.splitlines()[0] if body else "[Fusebox] proposed fix"
    if token is None:
        return {"dry_run": True, "repo": repo, "branch": branch,
                "base": base, "title": title, "body": body,
                "files": sorted(files)}
    api = _api or _GitHubAPI(token)
    head_sha = api.get_ref(repo, f"heads/{base}")
    api.create_ref(repo, f"refs/heads/{branch}", head_sha)
    blobs = {p: api.create_blob(repo, content) for p, content in files.items()}
    tree = api.create_tree(repo, head_sha, blobs)
    commit = api.create_commit(repo, title, tree, [head_sha])
    api.update_ref(repo, f"heads/{branch}", commit)
    pr = api.create_pr(repo, title, branch, base, body, draft=True)
    return {"dry_run": False, "pr_url": pr.get("html_url"), "pr_number": pr.get("number"),
            "branch": branch, "title": title}


class _GitHubAPI:
    def __init__(self, token: str):
        import httpx
        self._c = httpx.Client(base_url="https://api.github.com",
                               headers={"Authorization": f"Bearer {token}",
                                        "Accept": "application/vnd.github+json",
                                        "X-GitHub-Api-Version": "2022-11-28"},
                               timeout=30)

    def _check(self, r):
        r.raise_for_status()
        return r.json()

    def get_ref(self, repo: str, ref: str) -> str:
        return self._check(self._c.get(f"/repos/{repo}/git/ref/{ref}"))["object"]["sha"]

    def create_ref(self, repo: str, ref: str, sha: str) -> dict:
        return self._check(self._c.post(f"/repos/{repo}/git/refs",
                                        json={"ref": ref, "sha": sha}))

    def create_blob(self, repo: str, content: str) -> str:
        return self._check(self._c.post(f"/repos/{repo}/git/blobs",
                                        json={"content": base64.b64encode(content.encode()).decode(),
                                              "encoding": "base64"}))["sha"]

    def create_tree(self, repo: str, base_sha: str, blobs: dict[str, str]) -> str:
        tree = [{"path": p, "mode": "100644", "type": "blob", "sha": s}
                for p, s in blobs.items()]
        return self._check(self._c.post(f"/repos/{repo}/git/trees",
                                        json={"base_tree": base_sha, "tree": tree}))["sha"]

    def create_commit(self, repo: str, message: str, tree: str, parents: list[str]) -> str:
        return self._check(self._c.post(f"/repos/{repo}/git/commits",
                                        json={"message": message, "tree": tree,
                                              "parents": parents}))["sha"]

    def update_ref(self, repo: str, ref: str, sha: str) -> dict:
        return self._check(self._c.patch(f"/repos/{repo}/git/refs/{ref}",
                                         json={"sha": sha}))

    def create_pr(self, repo: str, title: str, head: str, base: str,
                  body: str, draft: bool) -> dict:
        return self._check(self._c.post(f"/repos/{repo}/pulls",
                                        json={"title": title, "head": head,
                                              "base": base, "body": body, "draft": draft}))
