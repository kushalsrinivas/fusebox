"""Incremental codebase indexer: chunk + embed + local vector search.

Pure stdlib (no numpy, no network). Qdrant/tree-sitter hook in later
without changing this interface: chunk_file -> embed -> store -> search.
"""

from .chunk import chunk_file, detect_lang
from .embed import HashEmbedder, cosine, tokenize
from .store import search_index
from .sync import list_repos, sync_repo

__all__ = [
    "chunk_file",
    "detect_lang",
    "HashEmbedder",
    "cosine",
    "tokenize",
    "search_index",
    "list_repos",
    "sync_repo",
]
