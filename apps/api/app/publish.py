"""Phase 0 publish stub: logs to stdout; Phase 2 swaps in real Redpanda producer."""

from .config import REDPANDA_BROKERS


def publish(topic: str, event: dict) -> None:
    if REDPANDA_BROKERS:
        # Real producer lands here in Phase 2 (kafka-python-ng). Keep fire-and-forget.
        print(f"[publish] {topic} brokers={REDPANDA_BROKERS} id={event.get('id')}")
    else:
        print(f"[publish:noop] {topic} id={event.get('id')}")
