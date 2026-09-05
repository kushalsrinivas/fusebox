"""Repo sync: local dir or git URL -> incremental chunk + upsert.

Incremental: content sha256 per file stored in meta.json; unchanged files
keep their chunks (no re-embed). Deleted files drop their vectors.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .chunk import ALLOW_EXTS, IGNORE_DIRS, chunk_file
from .store import load, upsert

CACHE_DIRNAME = ".cache"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _repo_name(repo_url: str, alias: str | None) -> str:
    if alias:
        return alias
    name = repo_url.rstrip("/").split("/")[-1]
    return name[:-4] if name.endswith(".git") else name or "repo"


def _is_local(repo_url: str) -> bool:
    return Path(repo_url).expanduser().exists()


def _pilignore(workdir: Path) -> list[str]:
    """Repo-level ignore file: blank lines/# comments, `dir/` prefixes,
    `*.ext` globs, exact rel paths. Merged over the built-in defaults."""
    f = workdir / ".pilignore"
    if not f.exists():
        return []
    pats = []
    for line in f.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pats.append(line)
    return pats


def _ignored(rel: str, pats: list[str]) -> bool:
    parts = Path(rel).parts
    if any(part in IGNORE_DIRS for part in parts):
        return True
    for pat in pats:
        if pat.endswith("/"):
            if rel == pat.rstrip("/") or rel.startswith(pat):
                return True
        elif "*" in pat:
            import fnmatch
            if fnmatch.fnmatch(Path(rel).name, pat):
                return True
        elif rel == pat or rel.startswith(pat.rstrip("/") + "/"):
            return True
    return False


def _ensure_checkout(repo_url: str, dest: Path) -> str | None:
    """Populate dest working copy. Returns HEAD sha for git repos, else None."""
    if _is_local(repo_url):
        src = Path(repo_url).expanduser().resolve()
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            if item.name in IGNORE_DIRS:
                continue
            target = dest / item.name
            if item.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(item, target, ignore=shutil.ignore_patterns(*IGNORE_DIRS))
            else:
                shutil.copy2(item, target)
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    if (dest / ".git").exists():
        subprocess.run(["git", "-C", str(dest), "fetch", "--depth", "50", "origin"],
                       capture_output=True)
        subprocess.run(["git", "-C", str(dest), "reset", "--hard", "origin/HEAD"],
                       capture_output=True)
    else:
        if dest.exists():
            shutil.rmtree(dest)
        subprocess.run(["git", "clone", "--depth", "50", repo_url, str(dest)],
                       check=True, capture_output=True)
    r = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"],
                       capture_output=True, text=True)
    return r.stdout.strip() or None


def _iter_source_files(workdir: Path) -> list[tuple[Path, str]]:
    out = []
    pats = _pilignore(workdir)
    for p in sorted(workdir.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in ALLOW_EXTS:
            continue
        rel = p.relative_to(workdir).as_posix()
        if _ignored(rel, pats):
            continue
        out.append((p, rel))
    return out


def _meta_path(root: str, tenant: str, repo: str) -> Path:
    return Path(root) / tenant / repo / "meta.json"


def _read_meta(root: str, tenant: str, repo: str) -> dict:
    f = _meta_path(root, tenant, repo)
    if f.exists():
        return json.loads(f.read_text())
    return {"files": {}}


def sync_repo(root: str, tenant: str, repo_url: str, alias: str | None = None) -> dict:
    repo = _repo_name(repo_url, alias)
    workdir = Path(root) / CACHE_DIRNAME / tenant / repo
    head = _ensure_checkout(repo_url, workdir)
    meta = _read_meta(root, tenant, repo)
    known: dict[str, str] = meta.get("files", {})
    if known and not load(root, tenant, repo) and _iter_source_files(workdir):
        # chunks lost but meta survived (wipe/upgrade): full re-embed, not empty index
        known = {}

    fresh: list[dict] = []
    current: dict[str, str] = {}
    changed = 0
    for abspath, rel in _iter_source_files(workdir):
        text = abspath.read_text(encoding="utf-8", errors="replace")
        h = _sha(text)
        current[rel] = h
        if known.get(rel) == h:
            continue
        changed += 1
        for c in chunk_file(str(abspath), rel):
            fresh.append({**c, "content_hash": h})

    # keep unchanged chunks from previous index without re-embedding
    if known:
        for c in load(root, tenant, repo):
            if c["path"] in current and current[c["path"]] == known.get(c["path"]):
                c.pop("vector", None)
                c.pop("tenant_id", None)
                c.pop("repo", None)
                fresh.append(c)

    removed = sorted(set(known) - set(current))
    n = upsert(root, tenant, repo, fresh)
    _meta_path(root, tenant, repo).parent.mkdir(parents=True, exist_ok=True)
    _meta_path(root, tenant, repo).write_text(json.dumps({
        "repo": repo,
        "repo_url": repo_url,
        "head_sha": head,
        "last_sync": datetime.now(timezone.utc).isoformat(),
        "files": current,
    }, indent=2))
    return {"repo": repo, "files": len(current), "changed": changed,
            "removed": removed, "chunks": n, "head_sha": head}


def list_repos(root: str, tenant: str) -> list[dict]:
    base = Path(root) / tenant
    if not base.exists():
        return []
    out = []
    for d in sorted(p for p in base.iterdir() if p.is_dir() and p.name != CACHE_DIRNAME):
        meta_file = d / "meta.json"
        meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
        n_chunks = sum(1 for _ in open(d / "chunks.jsonl")) if (d / "chunks.jsonl").exists() else 0
        out.append({"repo": d.name, "files": len(meta.get("files", {})),
                    "chunks": n_chunks, "last_sync": meta.get("last_sync"),
                    "head_sha": meta.get("head_sha")})
    # hide internal cache dir if tenant collides (defensive)
    return [r for r in out if r["repo"] != CACHE_DIRNAME]
