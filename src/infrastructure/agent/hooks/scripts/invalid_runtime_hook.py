"""Invalid runtime hook fixtures for security and audit tests."""

from __future__ import annotations


def return_invalid_type(payload: dict[str, object]) -> str:
    """Return an invalid type to exercise executor failure auditing."""
    _ = payload
    return "invalid"
