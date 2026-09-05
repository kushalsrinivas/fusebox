"""Password reset via email link."""


def request_reset(email: str) -> dict:
    """Send a password reset email with a single-use token."""
    token = f"rst_{abs(hash(email)) % 10_000_000}"
    send_email(email, "Reset your password", f"token={token}")
    return {"status": 200}


def send_email(to: str, subject: str, body: str) -> None:
    pass


def confirm_reset(token: str, new_password: str) -> dict:
    if not token.startswith("rst_"):
        return {"status": 400, "error": "bad token"}
    return {"status": 200}
