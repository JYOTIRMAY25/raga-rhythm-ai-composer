"""
Health check and system readiness endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from backend.app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System Health & Readiness Probe",
    description="Returns the operational health and readiness state of the API and DSP subsystems.",
)
async def get_health() -> HealthResponse:
    """
    Lightweight health check without executing heavy audio analysis.
    """
    return HealthResponse()
