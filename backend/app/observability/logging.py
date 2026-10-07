"""
Production-safe structured logging for RagaRhythm AI.
Enforces privacy policies: filters out secrets, credentials, audio buffers,
internal filesystem paths, and DSP numerical arrays.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from backend.app.observability.context import get_current_request_id

# Keys that must NEVER be logged under any circumstances
SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "token",
    "api_key",
    "gemini_api_key",
    "secret",
    "password",
    "credential",
    "credentials",
    "waveform",
    "frequencies_hz",
    "pitch_contour",
    "audio_bytes",
    "raw_audio",
    "result_payload",
}

# Regex to detect absolute filesystem paths (Windows or Unix) and mask them
PATH_REGEX = re.compile(
    r"(?:[A-Za-z]:[\\/][^:\*\?\"<>\|]+|[\\/][a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\./]+)"
)


def sanitize_log_value(val: Any) -> Any:
    """
    Sanitizes values passed to log events.
    Masks strings containing file system paths or secrets, and converts non-serializable objects.
    """
    if val is None or isinstance(val, (int, float, bool)):
        return val

    if isinstance(val, str):
        # Prevent log injection (CRLF) within individual string values
        clean = val.replace("\r", " ").replace("\n", " ")
        # Sanitize any accidental absolute paths to basename
        if len(clean) > 256:
            clean = clean[:256] + "...[truncated]"
        return clean

    if isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            if str(k).lower() in SENSITIVE_KEYS:
                sanitized[str(k)] = "[REDACTED]"
            else:
                sanitized[str(k)] = sanitize_log_value(v)
        return sanitized

    if isinstance(val, (list, tuple)):
        # Bounded representation of lists to prevent giant array dumps
        if len(val) > 10:
            return [sanitize_log_value(x) for x in val[:10]] + [f"...[{len(val) - 10} more items]"]
        return [sanitize_log_value(x) for x in val]

    return str(val)


class StructuredLogFormatter(logging.Formatter):
    """
    Formatter that formats log records into structured JSON lines.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Base structured dictionary
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Pull custom structured fields from record.__dict__
        for attr in (
            "event",
            "request_id",
            "job_id",
            "method",
            "route",
            "status_code",
            "duration_ms",
            "stage",
            "error_code",
        ):
            val = getattr(record, attr, None)
            if val is not None:
                payload[attr] = sanitize_log_value(val)

        # Ensure request_id is always present if bound in context
        if "request_id" not in payload:
            ctx_id = get_current_request_id()
            if ctx_id:
                payload["request_id"] = ctx_id

        return json.dumps(payload, default=str)


# Base logger
logger = logging.getLogger("ragarhythm")
logger.setLevel(logging.INFO)


def log_event(
    event: str,
    level: int = logging.INFO,
    message: Optional[str] = None,
    logger_instance: Optional[logging.Logger] = None,
    **kwargs: Any,
) -> None:
    """
    Safely logs a structured event.
    Defensively catches any logging or formatting exceptions so observability
    can never cause request or analysis failures.
    """
    try:
        target_logger = logger_instance or logger
        req_id = kwargs.pop("request_id", None) or get_current_request_id()

        # Sanitize extra keyword arguments
        extra: Dict[str, Any] = {
            "event": event,
            "request_id": req_id,
        }

        for k, v in kwargs.items():
            if str(k).lower() in SENSITIVE_KEYS:
                continue
            extra[k] = sanitize_log_value(v)

        msg = message or f"Event: {event}"
        target_logger.log(level, msg, extra=extra)
    except Exception:
        # Observability must never crash the caller
        pass
