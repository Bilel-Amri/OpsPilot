"""ISO-8601 timestamp helpers. Kubernetes resourceVersion is deliberately absent."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp and require an explicit timezone."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def timestamp_seconds(value: Any) -> float | None:
    parsed = parse_timestamp(value)
    return parsed.timestamp() if parsed else None
