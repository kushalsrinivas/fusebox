"""CSV export of user feedback."""


def export_feedback_csv(rows: list[dict]) -> str:
    """Export feedback rows (title, body, type) to CSV text."""
    lines = ["title,body,type"]
    for r in rows:
        lines.append(f"{r['title']},{r.get('body', '')},{r.get('type', 'other')}")
    return "\n".join(lines)
