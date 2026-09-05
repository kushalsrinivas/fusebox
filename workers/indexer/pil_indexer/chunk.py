"""Chunk source files into CodeUnit dicts.

Python uses stdlib `ast` (exact symbol + line ranges). Every other language
uses a heuristic top-level symbol scan, falling back to 200-line windows.
Tree-sitter can replace `_chunk_text` later behind the same return shape.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

MAX_WINDOW = 200

LANGS = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".sql": "sql",
}

ALLOW_EXTS = set(LANGS)
IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
    ".next",
    "vendor",
}

_TEXT_PATTERNS = [
    re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("),
    re.compile(r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?[\w$]*\s*=>"),
    re.compile(r"^(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"^(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"^(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*="),
    re.compile(r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)"),
]


def detect_lang(path: str) -> str | None:
    return LANGS.get(Path(path).suffix.lower())


def _header(rel: str, symbol: str, kind: str) -> str:
    return f"# {rel} :: {symbol} ({kind})\n"


def chunk_file(abspath: str, relpath: str) -> list[dict]:
    lang = detect_lang(relpath)
    if lang is None:
        return []
    try:
        text = Path(abspath).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    if lang == "python":
        return _chunk_python(text, relpath)
    return _chunk_text(text, relpath, lang)


def _chunk_python(text: str, rel: str) -> list[dict]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _windows(text.splitlines(), rel, "python")
    lines = text.splitlines()
    chunks: list[dict] = []

    def src(node: ast.AST) -> str:
        seg = ast.get_source_segment(text, node)
        if seg is not None:
            return seg
        return "\n".join(lines[(node.lineno - 1) : (node.end_lineno or node.lineno)])

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chunks.append(_make(rel, "python", node.name, "function", node.lineno,
                                node.end_lineno or node.lineno, src(node)))
        elif isinstance(node, ast.ClassDef):
            start = node.lineno
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    chunks.append(_make(rel, "python", f"{node.name}.{item.name}",
                                        "method", item.lineno,
                                        item.end_lineno or item.lineno, src(item)))
            chunks.append(_make(rel, "python", node.name, "class", start,
                                node.end_lineno or start, src(node)))
    if not chunks:
        return _windows(lines, rel, "python")
    return chunks


def _chunk_text(text: str, rel: str, lang: str) -> list[dict]:
    lines = text.splitlines()
    marks: list[tuple[int, str]] = []  # (lineno 1-based, symbol)
    for i, line in enumerate(lines):
        s = line.strip()
        for pat in _TEXT_PATTERNS:
            m = pat.match(s)
            if m:
                marks.append((i + 1, m.group(1)))
                break
    if not marks:
        return _windows(lines, rel, lang)
    chunks: list[dict] = []
    preamble = lines[: marks[0][0] - 1]
    if sum(1 for l in preamble if l.strip()) > 3:
        chunks.append(_make(rel, lang, "__header__", "file", 1, marks[0][0] - 1,
                            "\n".join(preamble)))
    for idx, (start, symbol) in enumerate(marks):
        end = (marks[idx + 1][0] - 1) if idx + 1 < len(marks) else len(lines)
        body = lines[start - 1 : end]
        if len(body) > MAX_WINDOW:
            for w, part in enumerate(_split_windows(body, MAX_WINDOW)):
                chunks.append(_make(rel, lang, f"{symbol}~p{w}", "function",
                                    start + w * MAX_WINDOW,
                                    start + w * MAX_WINDOW + len(part) - 1,
                                    "\n".join(part)))
        else:
            chunks.append(_make(rel, lang, symbol, "function", start, end,
                                "\n".join(body)))
    return chunks


def _split_windows(body: list[str], size: int) -> list[list[str]]:
    return [body[i : i + size] for i in range(0, len(body), size)]


def _windows(lines: list[str], rel: str, lang: str) -> list[dict]:
    return [
        _make(rel, lang, f"__part{i}__", "file", i * MAX_WINDOW + 1,
              i * MAX_WINDOW + len(part), "\n".join(part))
        for i, part in enumerate(_split_windows(lines, MAX_WINDOW))
    ]


def _make(rel: str, lang: str, symbol: str, kind: str,
          start: int, end: int, code: str) -> dict:
    return {
        "path": rel,
        "lang": lang,
        "symbol": symbol,
        "kind": kind,
        "start_line": start,
        "end_line": end,
        "content": _header(rel, symbol, kind) + code,
    }
