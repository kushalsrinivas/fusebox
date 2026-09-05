"""Order total calculation: subtotal, discount, tax."""


def order_total(items: list[dict], discount_pct: float = 0.0, tax_pct: float = 0.0) -> int:
    """Return total in cents: sum(qty*price) - discount + tax."""
    subtotal = sum(i["qty"] * i["price_cents"] for i in items)
    after_discount = subtotal * (1 - discount_pct / 100)
    return int(after_discount * (1 + tax_pct / 100))


def apply_coupon(code: str) -> float:
    """Map coupon code to discount percent."""
    return {"WELCOME10": 10.0}.get(code.upper(), 0.0)
