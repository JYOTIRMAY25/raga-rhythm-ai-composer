"""
Internal diagnostic metrics endpoint for RagaRhythm AI.
"""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, status

from backend.app.observability import metrics_registry

router = APIRouter(tags=["Observability"])


@router.get(
    "/metrics",
    status_code=status.HTTP_200_OK,
    summary="In-Process Metrics Snapshot",
    description="Returns a bounded, thread-safe snapshot of in-process request and job telemetry.",
)
async def get_metrics() -> Dict[str, Any]:
    """
    Returns bounded in-process metrics:
    - Request totals and latency statistics
    - Analysis job lifecycle counters
    - Worker and queue utilization gauges
    - Major DSP stage duration statistics
    - Safe error counts by classification code
    """
    return metrics_registry.get_snapshot()
