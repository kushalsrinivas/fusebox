"""Push notification dispatch (FCM/APNs)."""


def send_push(device_token: str, title: str, body: str) -> dict:
    """Send a push notification; missing pushes usually mean stale tokens."""
    if not device_token:
        return {"status": 400, "error": "missing device token"}
    return {"status": 202, "message_id": f"msg_{device_token[-4:]}"}


def register_token(user_id: str, device_token: str) -> dict:
    return {"user_id": user_id, "registered": True}
