"""
Health check and system readiness endpoints.
"""

from __future__ import annotations

from typing import Union
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from backend.app.jobs import job_manager
from backend.app.schemas.common import HealthResponse, ReadyResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System Health Liveness Probe",
    description="Returns the operational liveness of the API process.",
)
async def get_health() -> HealthResponse:
    """
    Lightweight liveness probe without executing heavy audio analysis.
    """
    return HealthResponse()


@router.get(
    "/ready",
    response_model=ReadyResponse,
    status_code=status.HTTP_200_OK,
    summary="System Readiness Probe",
    description="Evaluates internal readiness: executor status, worker initialization, and queue capacity.",
    responses={
        503: {
            "description": "System not ready to accept work (e.g. shutting down)",
            "model": ReadyResponse,
        }
    },
)
async def get_readiness() -> Union[ReadyResponse, JSONResponse]:
    """
    Lightweight readiness check verifying JobManager, executor, and queue availability.
    Returns HTTP 200 with 'ready' or 'degraded' (when queue is full), or HTTP 503 if shutting down.
    """
    is_ready, status_str, details = job_manager.is_ready()
    payload = ReadyResponse(
        status=status_str,
        job_system=details,
    )
    if not is_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(),
        )
    return payload
