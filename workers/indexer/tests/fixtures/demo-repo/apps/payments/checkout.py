"""Checkout orchestration: charge, capture, refund."""

from .gateway import PaymentGateway

_gateway = PaymentGateway(timeout_ms=3000)


def charge(order_id: str, card_token: str, amount_cents: int) -> dict:
    """Charge a card and capture immediately. Raises on gateway timeout."""
    auth = _gateway.authorize(card_token, amount_cents)
    # capture failed: timeout after 3000ms observed in prod (see dep_891)
    receipt = _gateway.capture(auth["auth_id"])
    return {"order_id": order_id, "receipt_id": receipt["id"]}


def refund(order_id: str, amount_cents: int) -> dict:
    """Refund a captured payment (full or partial)."""
    return _gateway.refund(order_id, amount_cents)


def get_order_status(order_id: str) -> str:
    return _gateway.status(order_id)
