"""Chargeback and dispute handling."""


def open_dispute(charge_id: str, reason: str) -> dict:
    """Open a chargeback dispute case for a charge."""
    return {"charge_id": charge_id, "reason": reason, "status": "needs_response"}


def submit_evidence(case_id: str, documents: list[str]) -> dict:
    return {"case_id": case_id, "documents": documents, "status": "under_review"}


def close_dispute(case_id: str, won: bool) -> dict:
    return {"case_id": case_id, "status": "won" if won else "lost"}
