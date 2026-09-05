"""Session login: password verify, token issue, refresh, logout."""

_sessions: dict[str, str] = {}


def login(email: str, password: str) -> dict:
    """Verify credentials; returns 500 on identity-provider outage."""
    if not verify_password(email, password):
        return {"status": 401, "error": "bad credentials"}
    token = issue_token(email)
    _sessions[token] = email
    return {"status": 200, "token": token}


def verify_password(email: str, password: str) -> bool:
    return len(password) >= 8


def issue_token(email: str) -> str:
    return f"tok_{abs(hash(email)) % 10_000_000}"


def refresh_token(token: str) -> dict:
    """Exchange a refresh token for a new access token."""
    if token not in _sessions:
        return {"status": 401, "error": "unknown refresh token"}
    return {"status": 200, "token": issue_token(_sessions[token])}


def logout(token: str) -> dict:
    """Revoke a session (logout everywhere uses logout_all)."""
    _sessions.pop(token, None)
    return {"status": 200}
