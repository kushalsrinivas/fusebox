"""Local vector store: one JSONL file per tenant/repo.

`<root>/<tenant>/<repo>/chunks.jsonl` — each line is a chunk + vector.
Qdrant replaces this backend in Phase 3 behind `upsert`/`search_index`;
chunk schema stays identical.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from .embed import HashEmbedder, cosine, tokenize

_embedder = HashEmbedder()


def _repo_dir(root: str, tenant: str, repo: str) -> Path:
    d = Path(root) / tenant / repo
    d.mkdir(parents=True, exist_ok=True)
    return d


def upsert(root: str, tenant: str, repo: str, chunks: list[dict]) -> int:
    path = _repo_dir(root, tenant, repo) / "chunks.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for c in chunks:
            vec = _embedder.embed(c["content"])
            f.write(json.dumps({**c, "tenant_id": tenant, "repo": repo, "vector": vec}) + "\n")
    return len(chunks)


def load(root: str, tenant: str, repo: str | None = None) -> list[dict]:
    base = Path(root) / tenant
    if not base.exists():
        return []
    repos = [repo] if repo else [p.name for p in base.iterdir() if p.is_dir()]
    out: list[dict] = []
    for r in repos:
        f = base / r / "chunks.jsonl"
        if not f.exists():
            continue
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    return out


def _stem_hit(query_tok: str, hay_tokens: set[str]) -> bool:
    """Exact, substring, or shared-prefix (>=4 chars) match.

    Catches morphological variants like limiting<->limit without a stemmer dep.
    """
    if len(query_tok) < 3:
        return query_tok in hay_tokens
    for h in hay_tokens:
        if query_tok == h or query_tok in h or h in query_tok:
            return True
        if len(h) >= 4 and (h.startswith(query_tok[:4]) and query_tok.startswith(h[:4])):
            if query_tok.startswith(h) or h.startswith(query_tok):
                return True
    return False


def _symbol_boost(query_tokens: set[str], chunk: dict) -> float:
    if not query_tokens:
        return 0.0
    hay = f"{chunk['path']} {chunk['symbol']}".lower().replace("/", " ").replace(".", " ")
    hay_tokens = set(hay.split()) | set(tokenize(chunk["symbol"]))
    hit = sum(1 for t in query_tokens if _stem_hit(t, hay_tokens))
    return hit / len(query_tokens)


def search_index(root: str, tenant: str, query: str, top_k: int = 8,
                 repo: str | None = None) -> list[dict]:
    chunks = load(root, tenant, repo)
    if not chunks:
        return []
    qvec = _embedder.embed(query)
    qtokens = set(tokenize(query))

    # IDF over the tenant corpus: terms like "token" that appear in many
    # chunks (auth code) must not outrank rare discriminative terms
    # ("bucket", "chargeback") that pinpoint the right file.
    doc_tokens = [set(tokenize(c["content"][:2000])) for c in chunks]
    n_docs = len(doc_tokens) or 1
    idf = {}
    for t in qtokens:
        df = sum(1 for dt in doc_tokens if t in dt)
        idf[t] = math.log((n_docs + 1) / (df + 1)) + 1.0
    idf_sum = sum(idf.values()) or 1.0

    scored = []
    for c, ctokens in zip(chunks, doc_tokens):
        cos = cosine(qvec, c["vector"])
        covered = sum(idf[t] for t in qtokens if t in ctokens)
        coverage = covered / idf_sum
        boost = _symbol_boost(qtokens, c)
        score = 0.40 * cos + 0.35 * coverage + 0.25 * boost
        scored.append((score, c))
    scored.sort(key=lambda s: s[0], reverse=True)
    hits = []
    for score, c in scored[:top_k]:
        hits.append({
            "path": c["path"],
            "repo": c["repo"],
            "symbol": c["symbol"],
            "kind": c["kind"],
            "lines": f"{c['start_line']}-{c['end_line']}",
            "excerpt": c["content"][:600],
            "ref": f"index://{c['repo']}/{c['path']}#L{c['start_line']}-L{c['end_line']}",
            "score": round(score, 4),
        })
    return hits
