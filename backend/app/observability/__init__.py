"""
Observability and reliability package for RagaRhythm AI.
Provides structured logging, request correlation, monotonic stage timing,
and bounded thread-safe in-process metrics.
"""

from backend.app.observability.context import (
    SAFE_REQUEST_ID_REGEX,
    get_current_request_id,
    reset_current_request_id,
    sanitize_request_id,
    set_current_request_id,
)
from backend.app.observability.logging import (
    StructuredLogFormatter,
    log_event,
    logger,
)
from backend.app.observability.metrics import (
    MetricsRegistry,
    metrics_registry,
)
from backend.app.observability.timing import (
    StageTimer,
    StageTimerScope,
)

__all__ = [
    "SAFE_REQUEST_ID_REGEX",
    "get_current_request_id",
    "set_current_request_id",
    "reset_current_request_id",
    "sanitize_request_id",
    "StructuredLogFormatter",
    "log_event",
    "logger",
    "MetricsRegistry",
    "metrics_registry",
    "StageTimer",
    "StageTimerScope",
]
