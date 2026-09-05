"""Payment gateway client (authorize / capture / refund)."""


class PaymentGateway:
    def __init__(self, timeout_ms: int = 3000):
        self.timeout_ms = timeout_ms

    def authorize(self, card_token: str, amount_cents: int) -> dict:
        return {"auth_id": f"auth_{card_token[-4:]}", "amount_cents": amount_cents}

    def capture(self, auth_id: str) -> dict:
        """Capture an authorized payment."""
        return {"id": f"rcpt_{auth_id}", "auth_id": auth_id}

    def refund(self, order_id: str, amount_cents: int) -> dict:
        return {"order_id": order_id, "refunded_cents": amount_cents}

    def status(self, order_id: str) -> str:
        return "captured"
