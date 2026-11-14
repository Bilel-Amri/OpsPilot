"""Canonical JSON hashing for OpsPilot evidence payloads."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_payload_bytes(payload: Any) -> bytes:
    """Serialize JSON-compatible data deterministically.

    Hashes are calculated over the normalized `payload` only, not over the
    EvidenceItem metadata. Object keys are sorted and whitespace is removed.
    """
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Payload is not valid JSON data: {exc}") from exc
    return encoded.encode("utf-8")


def calculate_payload_hash(payload: Any) -> str:
    """Return the lowercase SHA-256 hex digest of a normalized payload."""
    return hashlib.sha256(canonical_payload_bytes(payload)).hexdigest()


def verify_payload_hash(payload: Any, expected_hash: str) -> bool:
    """Compare a supplied digest with the digest calculated from payload."""
    if not isinstance(expected_hash, str):
        return False
    normalized = expected_hash.removeprefix("sha256:").strip().lower()
    if len(normalized) != 64:
        return False
    try:
        int(normalized, 16)
        actual = calculate_payload_hash(payload)
    except (ValueError, TypeError):
        return False
    return actual == normalized
