"""
Request context and correlation identifier management for RagaRhythm AI.
Provides request-safe contextvars and rigorous validation to defend against
log injection, control characters, and unbounded header lengths.
"""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar, Token
from typing import Optional

# Safe request ID pattern: alphanumeric characters, hyphens, and underscores only.
# Maximum length bounded to 64 characters to prevent memory exhaustion or logging bloat.
SAFE_REQUEST_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_REQUEST_ID_LENGTH = 64

# Request-scoped context variable
_current_request_id: ContextVar[Optional[str]] = ContextVar(
    "current_request_id", default=None
)


def sanitize_request_id(raw_id: Optional[str]) -> str:
    """
    Validates and sanitizes a client-provided or generated request correlation ID.

    Security rules:
    - Rejects None, empty, or whitespace-only inputs -> generates new UUID4.
    - Strips leading/trailing whitespace.
    - Enforces strict character allowlist: [A-Za-z0-9_-].
    - Defends against log/header injection by rejecting newlines, carriage returns,
      ANSI escape codes, null bytes, and non-printable control characters.
    - Rejects strings exceeding MAX_REQUEST_ID_LENGTH (64 characters).
    - If validation fails, safely generates and returns a new random UUID4.
    """
    if raw_id is None:
        return str(uuid.uuid4())

    cleaned = raw_id.strip()
    if not cleaned:
        return str(uuid.uuid4())

    # Fast character check for control characters or newlines
    if any(ord(c) < 32 or ord(c) >= 127 for c in cleaned):
        return str(uuid.uuid4())

    if len(cleaned) > MAX_REQUEST_ID_LENGTH:
        return str(uuid.uuid4())

    if not SAFE_REQUEST_ID_REGEX.match(cleaned):
        return str(uuid.uuid4())

    return cleaned


def get_current_request_id() -> Optional[str]:
    """Retrieves the request correlation ID associated with the current async task context."""
    return _current_request_id.get()


def set_current_request_id(request_id: str) -> Token[Optional[str]]:
    """
    Sets the request correlation ID for the current context.
    Returns a reset token that must be used to restore the previous context.
    """
    sanitized = sanitize_request_id(request_id)
    return _current_request_id.set(sanitized)


def reset_current_request_id(token: Token[Optional[str]]) -> None:
    """Restores the request correlation ID contextvar using the provided token."""
    _current_request_id.reset(token)
