"""
Common response and error schemas for RagaRhythm AI API.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """System health check and engine readiness payload."""
    model_config = ConfigDict(extra="forbid")

    status: str = Field(default="healthy", description="Overall system health status ('healthy', 'degraded')")
    version: str = Field(default="1.0.0", description="API semantic version")
    services: Dict[str, str] = Field(
        default_factory=lambda: {
            "api": "operational",
            "dsp_engine": "available",
            "dataset_adapter": "ready",
            "tala_engine": "available",
            "raga_engine": "available",
        },
        description="Individual subsystem operational states"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp of the health check"
    )


class ErrorDetailResponse(BaseModel):
    """RFC-compliant structured error response."""
    model_config = ConfigDict(extra="forbid")

    error_code: str = Field(..., description="Unique machine-readable error identifier")
    message: str = Field(..., description="Human-readable error description (sanitized)")
    status_code: int = Field(..., description="HTTP status code")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional context or validation details")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp when error occurred"
    )


class NotImplementedResponse(BaseModel):
    """Structured response for planned endpoints not yet implemented."""
    model_config = ConfigDict(extra="forbid")

    status: str = Field(default="not_implemented", description="Status code string")
    error_code: str = Field(default="FEATURE_NOT_IMPLEMENTED", description="Standardized error code")
    message: str = Field(..., description="Explanation of future capability and roadmap")
    endpoint: str = Field(..., description="Requested endpoint URI")
    documentation_ref: str = Field(
        default="docs/API_SPEC.md",
        description="Reference documentation for specification contract"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp"
    )
