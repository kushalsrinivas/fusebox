import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pil_indexer.chunk import chunk_file  # noqa: E402

FIX = Path(__file__).parent / "fixtures" / "demo-repo"


def test_python_ast_symbols():
    chunks = chunk_file(str(FIX / "apps/payments/checkout.py"),
                        "apps/payments/checkout.py")
    syms = {c["symbol"] for c in chunks}
    assert {"charge", "refund", "get_order_status"} <= syms
    charge = next(c for c in chunks if c["symbol"] == "charge")
    assert charge["kind"] == "function"
    assert charge["start_line"] >= 1 and charge["end_line"] > charge["start_line"]
    assert "capture" in charge["content"]


def test_python_methods_qualified():
    chunks = chunk_file(str(FIX / "apps/payments/gateway.py"),
                        "apps/payments/gateway.py")
    syms = {c["symbol"] for c in chunks}
    assert "PaymentGateway.capture" in syms


def test_typescript_heuristic():
    chunks = chunk_file(str(FIX / "apps/feed/timeline.ts"), "apps/feed/timeline.ts")
    syms = {c["symbol"] for c in chunks}
    assert {"getTimeline", "rankFeed"} <= syms


def test_sql_falls_back_to_windows():
    chunks = chunk_file(str(FIX / "infra/schema.sql"), "infra/schema.sql")
    assert chunks, "expected at least one chunk"
    assert all(c["start_line"] >= 1 for c in chunks)
    assert any("users" in c["content"] for c in chunks)
