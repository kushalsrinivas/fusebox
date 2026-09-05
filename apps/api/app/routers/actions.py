"""Engineering actions: propose diff -> validate -> sandbox -> risk -> approve -> draft PR.

Guards: denylisted paths and secrets are rejected at propose time (stored for
audit); high-risk actions need explicit second confirmation at approve time;
external writes (GitHub draft PR) happen only on approve, dry-run otherwise.
"""

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db, quotas
from ..auth import tenant_from_key

router = APIRouter()


def _roots():
    here = os.path.dirname(__file__)
    idx = os.path.abspath(os.getenv(
        "PIL_INDEX_ROOT",
        os.path.join(here, "..", "..", "..", "workers", "indexer", ".pil-index")))
    return idx


def _working_copy(tenant_id: str, repo: str) -> dict[str, str]:
    """Base files for sandboxing: the indexer's cached checkout."""
    workdir = Path(_roots()) / ".cache" / tenant_id / repo
    if not workdir.exists():
        raise HTTPException(status_code=422,
                            detail=f"unknown repo '{repo}': sync it first via POST /v1/repos/sync")
    try:
        from pil_indexer.chunk import ALLOW_EXTS, IGNORE_DIRS
    except ImportError:
        ALLOW_EXTS, IGNORE_DIRS = {".py"}, set()
    files = {}
    for p in sorted(workdir.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in ALLOW_EXTS:
            continue
        rel = p.relative_to(workdir).as_posix()
        if any(part in IGNORE_DIRS for part in Path(rel).parts):
            continue
        files[rel] = p.read_text(encoding="utf-8", errors="replace")
    if not files:
        raise HTTPException(status_code=422, detail=f"repo '{repo}' has no indexable files")
    return files


def _refcounts(tenant_id: str, touched: list[str]) -> dict[str, int]:
    """How many indexed chunks import each touched file (blast-radius input)."""
    try:
        from pil_indexer.store import load
    except ImportError:
        return {}
    try:
        chunks = load(_roots(), tenant_id)
    except Exception:
        return {}
    counts = {}
    for p in touched:
        stem = Path(p).stem
        dotted = Path(p).with_suffix("").as_posix().replace("/", ".")
        variants = {stem, dotted, dotted.split(".", 1)[-1] if "." in dotted else dotted}
        n = 0
        for c in chunks:
            if c.get("path") == p:
                continue
            for line in c.get("content", "").splitlines():
                s = line.strip()
                if s.startswith(("import ", "from ")) and any(v in s for v in variants):
                    n += 1
                    break
        counts[p] = n
    return counts


class ProposeIn(BaseModel):
    cluster_id: str = Field(min_length=1)
    repo: str = Field(min_length=1, max_length=200)
    diff: str = Field(min_length=1, max_length=100_000)
    title: str | None = Field(default=None, max_length=200)


@router.post("/v1/actions/propose")
def propose_action(payload: ProposeIn, tenant_id: str = Depends(tenant_from_key)):
    from action.diff import changed_paths, diff_size, parse_diff, validate_diff
    from action.risk import score_risk
    from action.sandbox import run_checks
    from action.secrets import scan_diff

    cluster = db.get_cluster(tenant_id, payload.cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="cluster not found")
    inv = db.latest_investigation(tenant_id, cluster["id"])

    def _reject(status: str, detail: str):
        row = db.save_action(tenant_id, {
            "cluster_id": cluster["id"],
            "investigation_id": inv["id"] if inv else None,
            "repo": payload.repo, "branch": "", "title": payload.title or "",
            "diff": payload.diff, "status": status,
            "risk": {}, "sandbox": {"logs": [detail]}, "dry_run": True})
        raise HTTPException(status_code=422, detail={"error": detail, "action_id": row["id"]})

    issues = validate_diff(payload.diff)
    if issues:
        _reject("rejected_by_policy", "; ".join(issues))
    hits = scan_diff(payload.diff)
    if hits:
        _reject("rejected_by_policy",
                f"secrets in diff: {', '.join(h['kind'] for h in hits)}")

    base = _working_copy(tenant_id, payload.repo)
    sandbox = run_checks(base, payload.diff)
    quotas.check("actions", tenant_id)
    paths = changed_paths(parse_diff(payload.diff))
    risk = score_risk(paths, _refcounts(tenant_id, paths), diff_lines=diff_size(payload.diff))

    top = ((inv or {}).get("result") or {}).get("hypotheses", [{}])[0]
    sha = (top.get("commit_sha") or "manual")[:7]
    branch = f"fuse/{cluster['key']}-{sha}"
    row = db.save_action(tenant_id, {
        "cluster_id": cluster["id"], "investigation_id": inv["id"] if inv else None,
        "repo": payload.repo, "branch": branch,
        "title": payload.title or f"[Fusebox] {cluster['title']}",
        "diff": payload.diff,
        "status": "sandbox_passed" if sandbox["ok"] else "sandbox_failed",
        "risk": risk, "sandbox": {"ok": sandbox["ok"], "logs": sandbox["logs"]},
        "dry_run": True})
    quotas.bump("actions", tenant_id)
    return {"action": row, "risk": risk, "sandbox": sandbox}


@router.get("/v1/actions")
def get_actions(cluster_id: str | None = None,
                tenant_id: str = Depends(tenant_from_key)):
    return {"items": db.list_actions(tenant_id, cluster_id)}


@router.get("/v1/actions/{aid}")
def get_action(aid: str, tenant_id: str = Depends(tenant_from_key)):
    row = db.get_action(tenant_id, aid)
    if row is None:
        raise HTTPException(status_code=404, detail="action not found")
    return row


class ApproveIn(BaseModel):
    github_repo: str | None = Field(default=None, max_length=200)
    confirm_high_risk: bool = False


@router.post("/v1/actions/{aid}/approve")
def approve_action(aid: str, payload: ApproveIn,
                   tenant_id: str = Depends(tenant_from_key)):
    from action.diff import apply_diff, changed_paths, parse_diff
    from action.pr import build_pr_body, open_draft_pr

    row = db.get_action(tenant_id, aid)
    if row is None:
        raise HTTPException(status_code=404, detail="action not found")
    if row["status"] != "sandbox_passed":
        raise HTTPException(status_code=422,
                            detail=f"action is {row['status']}; only sandbox_passed can be approved")
    risk = row.get("risk") or {}
    if risk.get("requires_two_approvals") and not payload.confirm_high_risk:
        raise HTTPException(status_code=422, detail={
            "error": f"high regression risk ({risk.get('score')}); "
                     "re-approve with confirm_high_risk=true",
            "factors": risk.get("factors", [])})

    cluster = db.get_cluster(tenant_id, row["cluster_id"]) if row.get("cluster_id") else None
    inv = db.latest_investigation(tenant_id, row["cluster_id"]) if row.get("cluster_id") else None
    result = (inv or {}).get("result", {}) if isinstance(inv, dict) else {}
    top = (result.get("hypotheses") or [{}])[0]

    base = _working_copy(tenant_id, row["repo"])
    merged = apply_diff(base, row["diff"])
    files = {p: merged[p] for p in changed_paths(parse_diff(row["diff"])) if p in merged}
    body = build_pr_body((cluster or {}).get("title", row["title"]), top,
                         risk, row.get("sandbox") or {}, row["repo"])

    token = os.getenv("PIL_GITHUB_TOKEN")
    if token and payload.github_repo and "/" in payload.github_repo:
        opened = open_draft_pr(payload.github_repo, row["branch"], files, body, token)
        pr_url, dry = opened.get("pr_url"), False
    else:
        opened = open_draft_pr(row["repo"], row["branch"], files, body, None)
        pr_url, dry = None, True
    updated = db.update_action(tenant_id, aid, {
        "status": "approved", "pr_url": pr_url, "dry_run": dry,
        "sandbox": {**(row.get("sandbox") or {}),
                     "pr": {"dry_run": dry, "pr_url": pr_url,
                            "title": opened.get("title"), "files": opened.get("files")}}})
    db.log_audit(tenant_id, tenant_id, "action_approved",
                 {"action_id": aid, "branch": row["branch"],
                  "pr_url": pr_url, "dry_run": dry,
                  "risk": risk.get("level"), "github_repo": payload.github_repo})
    return {"action": updated, "pr": opened}
