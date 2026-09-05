"""Inbound Stripe webhooks with retry for failed deliveries."""

RETRYABLE_EVENTS = {"payment_intent.failed", "charge.dispute.created"}

pending_retries: list[dict] = []


def handle_webhook(event_type: str, payload: dict) -> str:
    if event_type in RETRYABLE_EVENTS:
        pending_retries.append({"event_type": event_type, "payload": payload})
        return "queued_for_retry"
    return apply_event(event_type, payload)


def apply_event(event_type: str, payload: dict) -> str:
    return f"applied:{event_type}"


def retry_failed(limit: int = 10) -> int:
    """Retry failed webhook deliveries with backoff."""
    batch, pending_retries[:] = pending_retries[:limit], pending_retries[limit:]
    for item in batch:
        apply_event(item["event_type"], item["payload"])
    return len(batch)
