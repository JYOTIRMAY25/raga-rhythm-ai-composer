"""
Audio analysis endpoints executing the asynchronous DSP job pipeline.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile, status

from backend.app.core.exceptions import (
    AudioDurationExceededError,
    AudioValidationError,
    JobNotFoundError,
    JobQueueFullError,
)
from backend.app.core.security import save_upload_to_storage
from backend.app.jobs import (
    AnalysisJobCancelResponse,
    AnalysisJobStatusResponse,
    job_manager,
)

router = APIRouter(tags=["Analysis"])


@router.post(
    "/analyze",
    response_model=AnalysisJobStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit Audio Recording for Asynchronous Analysis",
    description="Uploads and enqueues an Indian classical music audio recording for asynchronous background analysis, returning a trackable job ID immediately.",
)
async def analyze_audio(
    request: Request,
    file: UploadFile = File(..., description="Audio file in MP3, WAV, FLAC, OGG, or M4A format (max 25 MB)"),
) -> AnalysisJobStatusResponse:
    """
    Validates the uploaded audio file and enqueues an asynchronous analysis job.
    Returns 202 Accepted with job metadata and initial QUEUED/PROCESSING state.
    """
    # Fast pre-check to reject uploads immediately when queue is saturated, avoiding wasted disk I/O
    if not job_manager.has_capacity():
        raise JobQueueFullError("Analysis queue is full. Please retry shortly.")

    req_id = getattr(request.state, "request_id", None)
    temp_path, original_filename, _ = await save_upload_to_storage(file)

    try:
        # Atomic creation and submission under lock prevents orphaned QUEUED jobs
        record = job_manager.create_and_submit_job(
            original_filename=original_filename,
            file_path=str(temp_path),
            request_id=req_id,
        )
        return record.to_status_response()
    except Exception:
        # Cleanup temp file on immediate queue or submission failure
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        raise


@router.get(
    "/analysis/{job_id}",
    response_model=AnalysisJobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Asynchronous Analysis Job Status",
    description="Retrieves the current execution progress, stage, and musical analysis result (when completed) for a submitted job ID.",
)
async def get_analysis_job(job_id: str) -> AnalysisJobStatusResponse:
    """
    Returns the real-time lifecycle status, progress (0-100), stage, error, or completed result payload.
    Uses atomic lock snapshot to guarantee status and progress consistency (Medium 1).
    """
    status_response = job_manager.get_job_status(job_id)
    if not status_response:
        raise JobNotFoundError(f"Analysis job '{job_id}' not found.")

    return status_response


@router.post(
    "/analysis/{job_id}/cancel",
    response_model=AnalysisJobCancelResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel In-Progress Analysis Job",
    description="Requests cancellation of an ongoing or queued audio analysis job.",
)
async def cancel_analysis_job(job_id: str) -> AnalysisJobCancelResponse:
    """
    Cooperatively cancels the specified job and purges temporary files.
    """
    new_status, message = job_manager.cancel_job(job_id)
    return AnalysisJobCancelResponse(
        job_id=job_id,
        status=new_status,
        message=message,
    )
