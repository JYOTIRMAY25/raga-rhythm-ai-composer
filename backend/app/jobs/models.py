"""
Domain models and state representations for asynchronous analysis jobs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.analysis import AnalysisResponse


class JobStatus(str, Enum):
    """Lifecycle states of an analysis job."""
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        """Returns True if this status is a final non-transitionable terminal state."""
        return self in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)


class JobError(BaseModel):
    """Sanitized, safe error description for failed jobs."""
    model_config = ConfigDict(extra="ignore")

    code: str = Field(..., description="Machine-readable error classification code")
    message: str = Field(..., description="Human-readable sanitized error message")


class AnalysisJobStatusResponse(BaseModel):
    """External API response representing current status of an analysis job."""
    model_config = ConfigDict(extra="ignore")

    job_id: str = Field(..., description="Unique job identifier UUID")
    status: JobStatus = Field(..., description="Current job lifecycle state")
    progress: int = Field(default=0, ge=0, le=100, description="Monotonically increasing progress percentage 0-100")
    current_stage: str = Field(default="Initialization", description="Current execution stage description")
    created_at: str = Field(..., description="ISO 8601 UTC creation timestamp")
    started_at: Optional[str] = Field(default=None, description="ISO 8601 UTC execution start timestamp")
    completed_at: Optional[str] = Field(default=None, description="ISO 8601 UTC completion or termination timestamp")
    result: Optional[AnalysisResponse] = Field(default=None, description="Analysis result payload when COMPLETED")
    error: Optional[JobError] = Field(default=None, description="Error details when FAILED")


class AnalysisJobCancelResponse(BaseModel):
    """Response returned when cancellation is requested on a job."""
    model_config = ConfigDict(extra="ignore")

    job_id: str = Field(..., description="Unique job identifier UUID")
    status: JobStatus = Field(..., description="Status after cancellation request")
    message: str = Field(..., description="Description of cancellation action taken")


class JobRecord:
    """
    Internal thread-safe state container for an asynchronous analysis job.
    """

    def __init__(
        self,
        job_id: str,
        original_filename: str,
        file_path: Optional[str] = None,
    ) -> None:
        self.job_id = job_id
        self.original_filename = original_filename
        self.file_path = file_path
        self.status = JobStatus.QUEUED
        self.progress: int = 0
        self.current_stage: str = "Initialization"
        self.created_at: datetime = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Optional[AnalysisResponse] = None
        self.error: Optional[JobError] = None
        self.cancel_requested: bool = False

    def to_status_response(self) -> AnalysisJobStatusResponse:
        """Serializes current job state into external Pydantic response schema."""
        return AnalysisJobStatusResponse(
            job_id=self.job_id,
            status=self.status,
            progress=self.progress,
            current_stage=self.current_stage,
            created_at=self.created_at.isoformat(),
            started_at=self.started_at.isoformat() if self.started_at else None,
            completed_at=self.completed_at.isoformat() if self.completed_at else None,
            result=self.result,
            error=self.error,
        )
