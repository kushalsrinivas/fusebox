"""Deterministic local embeddings (no network, no keys).

HashEmbedder: hashed token-frequency vectors, L2-normalized. Good enough for
Phase 1 grounding; swap for OpenAI/bge behind the same `.embed` interface in
Phase 3 without touching chunk/store/search.
"""

from __future__ import annotations

import hashlib
import math
import re

_WORD = re.compile(r"[a-z0-9]+")


def tokenize(s: str) -> list[str]:
    return _WORD.findall(s.lower())


class HashEmbedder:
    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        counts = [0.0] * self.dim
        for tok in tokenize(text):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            counts[h % self.dim] += 1.0
        # Sublinear TF (1 + log tf): stops a term repeated 10x in one chunk
        # (e.g. "token" in auth code) from drowning out rarer query terms.
        vec = [1.0 + math.log(c) if c > 0 else 0.0 for c in counts]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
