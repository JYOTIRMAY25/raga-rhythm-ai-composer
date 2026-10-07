"""
In-process Job Manager for asynchronous audio analysis pipeline execution.
Manages bounded ThreadPoolExecutor worker lifecycle, thread-safe state synchronization,
monotonic progress reporting, cooperative cancellation, temporary file isolation/cleanup,
and bounded TTL job retention.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from backend.app.analysis.pipeline import (
    AnalysisPipeline,
    UnifiedAnalysisResult,
)
from backend.app.analysis.preprocessor import (
    AudioPreprocessingError,
    AudioTooLongError,
    InvalidAudioError,
)
from backend.app.core.config import settings
from backend.app.core.exceptions import (
    AudioDurationExceededError,
    AudioValidationError,
    JobCancelledException,
    JobNotFoundError,
    JobQueueFullError,
)
from backend.app.jobs.models import (
    AnalysisJobCancelResponse,
    AnalysisJobStatusResponse,
    JobError,
    JobRecord,
    JobStatus,
)
from backend.app.schemas.analysis import (
    AnalysisResponse,
    AnalysisWarningSchema,
    AudioMetadataSchema,
    BeatGridSummarySchema,
    MotifEvidenceSchema,
    PitchSummarySchema,
    RagaAlternativeSchema,
    RagaResultSchema,
    RhythmSummarySchema,
    SwaraSummarySchema,
    TalaCandidateSchema,
    TalaResultSchema,
    TonicResultSchema,
)
from backend.app.observability import (
    get_current_request_id,
    log_event,
    metrics_registry,
)

logger = logging.getLogger("ragarhythm.jobs")


def format_analysis_response(
    analysis_id: str,
    result: UnifiedAnalysisResult,
    filename: str,
) -> AnalysisResponse:
    """Transforms internal UnifiedAnalysisResult into external API AnalysisResponse schema."""
    # Audio metadata
    audio_meta = AudioMetadataSchema(
        filename=filename,
        duration_seconds=result.audio_metadata.duration_seconds,
        sample_rate=result.audio_metadata.sample_rate,
        channels=result.audio_metadata.channels_original,
        format=os.path.splitext(filename)[1].replace(".", "").lower() if filename else "audio",
        is_silent=result.audio_metadata.is_silent,
        rms=result.audio_metadata.rms,
        peak_amplitude=result.audio_metadata.peak_amplitude,
    )

    # Tonic
    tonic = TonicResultSchema(
        frequency_hz=result.tonic.frequency_hz,
        note_name=result.tonic.note_name or "Unknown",
        octave=result.tonic.octave,
        cents_deviation=result.tonic.cents_deviation,
        confidence=result.tonic.confidence,
        is_ambiguous=result.tonic.is_ambiguous,
        runner_up_hz=result.tonic.runner_up_hz,
    )

    # Pitch
    pitch = PitchSummarySchema(
        total_frames=result.pitch.total_frames,
        voiced_frames=result.pitch.voiced_frames,
        voiced_percentage=result.pitch.voiced_percentage,
        frame_rate=result.pitch.frame_rate,
        mean_f0_hz=result.pitch.mean_f0_hz,
        min_f0_hz=result.pitch.min_f0_hz,
        max_f0_hz=result.pitch.max_f0_hz,
        method=result.pitch.method,
        downsampled_timestamps=result.pitch.downsampled_timestamps,
        downsampled_frequencies=result.pitch.downsampled_frequencies,
    )

    # Swara
    swara = SwaraSummarySchema(
        pitch_class_distribution=result.swara.pitch_class_distribution,
        active_swaras=result.swara.active_swaras,
        total_segments=result.swara.total_segments,
        mean_cents_deviation=result.swara.mean_cents_deviation,
        dominant_swaras=result.swara.dominant_swaras,
        transitions_top=result.swara.transitions_top,
    )

    # Raga
    raga_alts = [
        RagaAlternativeSchema(
            id=alt.raga_id,
            name=alt.name,
            thaat=alt.thaat,
            confidence=alt.confidence,
            composite_score=alt.composite_score,
        )
        for alt in result.raga.alternatives
    ]

    raga_motifs = [
        MotifEvidenceSchema(
            motif=mm.motif,
            motif_str=mm.motif_str,
            match_type=mm.match_type,
            matched_subsequence=mm.matched_subsequence,
            similarity_score=mm.similarity_score,
            start_time_seconds=mm.start_time_seconds,
            end_time_seconds=mm.end_time_seconds,
        )
        for mm in result.raga.motif_matches
    ]

    raga = RagaResultSchema(
        id=result.raga.predicted_raga_id,
        name=result.raga.predicted_raga,
        thaat=result.raga.thaat,
        time=result.raga.time,
        mood=result.raga.mood,
        vadi=result.raga.vadi,
        samvadi=result.raga.samvadi,
        aroha=result.raga.aroha,
        avaroha=result.raga.avaroha,
        confidence=result.raga.confidence,
        is_ambiguous=result.raga.is_ambiguous,
        alternatives=raga_alts,
        motif_matches=raga_motifs,
    )

    # Rhythm
    rhythm = RhythmSummarySchema(
        estimated_bpm=result.rhythm.estimated_bpm,
        laya=result.rhythm.laya,
        tempo_confidence=result.rhythm.tempo_confidence,
        total_onsets=result.rhythm.total_onsets,
        frame_rate=result.rhythm.frame_rate,
    )

    # Beat Grid
    beat_grid = BeatGridSummarySchema(
        beat_count=result.beat_grid.beat_count,
        beat_period=result.beat_grid.beat_period,
        bpm=result.beat_grid.bpm,
        confidence=result.beat_grid.confidence,
        selected_hypothesis=result.beat_grid.selected_hypothesis,
        first_beat_time=result.beat_grid.first_beat_time,
        sam_timestamps=result.beat_grid.sam_timestamps,
        cycle_length=result.beat_grid.cycle_length,
    )

    # Tala
    tala_cands = [
        TalaCandidateSchema(
            id=cand.tala_id,
            name=cand.name,
            matras=cand.matras,
            confidence=cand.confidence,
            composite_score=cand.composite_score,
        )
        for cand in result.tala.candidates
    ]

    tala = TalaResultSchema(
        id=result.tala.predicted_tala_id,
        name=result.tala.predicted_tala,
        matras=result.tala.matras,
        beats=result.tala.matras,
        vibhag_structure=result.tala.vibhag_structure,
        theka=result.tala.theka,
        sam_position=result.tala.sam_position,
        khali_positions=result.tala.khali_positions,
        tali_positions=result.tala.tali_positions,
        confidence=result.tala.confidence,
        is_ambiguous=result.tala.is_ambiguous,
        candidates=tala_cands,
        tempo_hypothesis=result.tala.tempo_hypothesis,
    )

    # Warnings
    warnings = [
        AnalysisWarningSchema(
            stage=w.stage,
            code=w.code,
            message=w.message,
        )
        for w in result.warnings
    ]

    return AnalysisResponse(
        analysis_id=analysis_id,
        status="completed",
        audio_metadata=audio_meta,
        tonic=tonic,
        pitch=pitch,
        swara=swara,
        raga=raga,
        rhythm=rhythm,
        beat_grid=beat_grid,
        tala=tala,
        warnings=warnings,
        processing_time_ms=result.processing_time_ms,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


class JobManager:
    """
    Thread-safe in-process manager for async analysis jobs.
    """

    def __init__(
        self,
        max_workers: Optional[int] = None,
        max_queued_jobs: Optional[int] = None,
        job_retention_seconds: Optional[int] = None,
        max_retained_jobs: Optional[int] = None,
        pipeline: Optional[AnalysisPipeline] = None,
    ) -> None:
        self._max_workers = max_workers or getattr(settings, "max_analysis_workers", 4)
        self._max_queued_jobs = max_queued_jobs or getattr(settings, "max_queued_jobs", 50)
        self._job_retention_seconds = job_retention_seconds or getattr(settings, "job_retention_seconds", 3600)
        self._max_retained_jobs = max_retained_jobs or getattr(settings, "max_retained_jobs", 1000)
        self._pipeline = pipeline or AnalysisPipeline()

        self._lock = threading.RLock()
        self._jobs: Dict[str, JobRecord] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="analysis_worker",
        )
        self._is_shutdown = False

        # Register thread-safe gauge provider for in-process metrics
        metrics_registry.set_gauge_provider(self._get_gauge_metrics)

    def _get_gauge_metrics(self) -> Dict[str, Any]:
        """Provides dynamic queue and worker gauges to metrics registry."""
        with self._lock:
            queued = sum(1 for j in self._jobs.values() if j.status == JobStatus.QUEUED)
            processing = sum(1 for j in self._jobs.values() if j.status == JobStatus.PROCESSING)
            active = queued + processing
            return {
                "queued_current": queued,
                "processing_current": processing,
                "active_total": active,
                "worker_capacity": self._max_workers,
                "workers_active": processing,
                "queue_capacity": self._max_queued_jobs,
                "queue_available": max(0, self._max_queued_jobs - active),
                "is_shutdown": self._is_shutdown,
            }

    def is_ready(self) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Inexpensive readiness probe verifying internal state:
        - JobManager initialized and not shutting down
        - ThreadPoolExecutor available
        - Queue capacity state
        """
        with self._lock:
            if self._is_shutdown:
                return False, "shutting_down", {"is_shutdown": True}

            active = sum(1 for j in self._jobs.values() if not j.status.is_terminal)
            available = max(0, self._max_queued_jobs - active)
            status_str = "ready" if available > 0 else "degraded"
            details = {
                "worker_capacity": self._max_workers,
                "queue_capacity": self._max_queued_jobs,
                "active_jobs": active,
                "queue_available": available,
            }
            return True, status_str, details

    def has_capacity(self) -> bool:
        """
        Thread-safe check whether the queue can accept an additional job.
        Does not permanently reserve capacity (authoritative reservation is inside create_job).
        Used as a fast pre-check before expensive audio upload streaming.
        """
        with self._lock:
            if self._is_shutdown:
                return False
            active_jobs_count = sum(
                1 for j in self._jobs.values() if not j.status.is_terminal
            )
            return active_jobs_count < self._max_queued_jobs

    def create_job(
        self,
        original_filename: str,
        file_path: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> JobRecord:
        """
        Creates and registers a new job in QUEUED state.
        Enforces queue bounding, retention eviction, and request correlation.
        """
        with self._lock:
            if self._is_shutdown:
                raise RuntimeError("JobManager has been shut down.")

            # Evict expired jobs before checking bounds
            self._cleanup_expired_jobs_locked()

            # Check queue capacity (count non-terminal jobs)
            active_jobs_count = sum(
                1 for j in self._jobs.values() if not j.status.is_terminal
            )
            if active_jobs_count >= self._max_queued_jobs:
                raise JobQueueFullError(
                    f"Job queue is full ({active_jobs_count}/{self._max_queued_jobs} active jobs). Please retry shortly."
                )

            # Enforce max retained jobs limit
            if len(self._jobs) >= self._max_retained_jobs:
                self._evict_oldest_terminal_job_locked()

            effective_request_id = request_id or get_current_request_id()
            job_id = str(uuid.uuid4())
            record = JobRecord(
                job_id=job_id,
                original_filename=original_filename,
                file_path=file_path,
                request_id=effective_request_id,
            )
            self._jobs[job_id] = record

            # Log lifecycle event and record metric
            try:
                log_event(
                    "analysis.job.created",
                    job_id=job_id,
                    request_id=effective_request_id,
                    status=JobStatus.QUEUED.value,
                )
            except Exception:
                pass

            try:
                metrics_registry.record_job_created()
            except Exception:
                pass

            return record

    def submit_job(self, job_id: str) -> JobRecord:
        """
        Submits a queued job to the worker thread pool.
        If submission fails (e.g. shutdown or executor rejection), marks the job as FAILED,
        restores queue capacity by setting terminal state, cleans up temp file, and raises.
        """
        with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                raise JobNotFoundError(f"Job {job_id} not found.")

            if record.status != JobStatus.QUEUED:
                return record

            log_event(
                "analysis.job.queued",
                job_id=job_id,
                request_id=record.request_id,
                status=JobStatus.QUEUED.value,
            )

            try:
                self._executor.submit(self._worker_execute, job_id)
            except Exception as exc:
                logger.error(f"Executor submission failed for job {job_id}: {exc}")
                record.status = JobStatus.FAILED
                record.current_stage = "Failed"
                record.completed_at = datetime.now(timezone.utc)
                record.error = JobError(
                    code="SUBMISSION_FAILED",
                    message="Failed to schedule audio analysis job on worker pool.",
                )
                self._cleanup_temp_file(record.file_path)
                metrics_registry.record_job_failed("SUBMISSION_FAILED")
                log_event(
                    "analysis.job.submission_failed",
                    level=logging.ERROR,
                    job_id=job_id,
                    request_id=record.request_id,
                    error_code="SUBMISSION_FAILED",
                )
                raise
            return record

    def create_and_submit_job(
        self,
        original_filename: str,
        file_path: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> JobRecord:
        """
        Atomically creates a job and submits it to the worker executor under lock.
        If executor submission fails, cleans up resources and guarantees the job
        does not remain in an orphaned QUEUED state.
        """
        with self._lock:
            record = self.create_job(
                original_filename=original_filename,
                file_path=file_path,
                request_id=request_id,
            )
            try:
                log_event(
                    "analysis.job.queued",
                    job_id=record.job_id,
                    request_id=record.request_id,
                    status=JobStatus.QUEUED.value,
                )
                self._executor.submit(self._worker_execute, record.job_id)
            except Exception as exc:
                logger.error(f"Executor submission failed for job {record.job_id}: {exc}")
                record.status = JobStatus.FAILED
                record.current_stage = "Failed"
                record.completed_at = datetime.now(timezone.utc)
                record.error = JobError(
                    code="SUBMISSION_FAILED",
                    message="Failed to schedule audio analysis job on worker pool.",
                )
                self._cleanup_temp_file(record.file_path)
                metrics_registry.record_job_failed("SUBMISSION_FAILED")
                log_event(
                    "analysis.job.submission_failed",
                    level=logging.ERROR,
                    job_id=record.job_id,
                    request_id=record.request_id,
                    error_code="SUBMISSION_FAILED",
                )
                raise
            return record

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        """Retrieves job record by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def get_job_status(self, job_id: str) -> Optional[AnalysisJobStatusResponse]:
        """
        Atomically snapshots the job's state into an immutable AnalysisJobStatusResponse schema
        while holding the lock. Prevents status/progress serialization races.
        """
        with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return None
            return record.to_status_response()

    def cancel_job(self, job_id: str) -> Tuple[JobStatus, str]:
        """
        Requests cooperative cancellation of a job.
        QUEUED -> immediately marked CANCELLED and file cleaned up.
        PROCESSING -> cancellation flag raised; worker aborts at next stage.
        Terminal -> returns existing terminal state.
        """
        with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                raise JobNotFoundError(f"Job {job_id} not found.")

            log_event(
                "analysis.job.cancel_requested",
                job_id=job_id,
                request_id=record.request_id,
                current_status=record.status.value,
            )

            if record.status == JobStatus.QUEUED:
                record.status = JobStatus.CANCELLED
                record.current_stage = "Cancelled"
                record.completed_at = datetime.now(timezone.utc)
                self._cleanup_temp_file(record.file_path)
                metrics_registry.record_job_cancelled()
                log_event(
                    "analysis.job.cancelled",
                    job_id=job_id,
                    request_id=record.request_id,
                    status=JobStatus.CANCELLED.value,
                    stage="Cancelled",
                )
                return JobStatus.CANCELLED, "Job was cancelled before execution started."

            if record.status == JobStatus.PROCESSING:
                record.cancel_requested = True
                return JobStatus.PROCESSING, "Cancellation requested for in-progress analysis."

            # Terminal states (COMPLETED, FAILED, CANCELLED)
            return record.status, f"Job has already reached terminal status: {record.status.value}."

    def update_progress(self, job_id: str, progress: int, stage: str) -> None:
        """
        Thread-safe monotonic progress update.
        Progress is strictly clamped to [0, 100] and cannot decrease.
        Cannot set 100% unless explicitly completed.
        """
        with self._lock:
            record = self._jobs.get(job_id)
            if not record or record.status.is_terminal:
                return

            clamped = max(0, min(99, int(progress)))
            if clamped > record.progress:
                record.progress = clamped
            record.current_stage = stage

    def complete_job(self, job_id: str, result: AnalysisResponse) -> None:
        """Transitions job to COMPLETED state and cleans up resources."""
        with self._lock:
            record = self._jobs.get(job_id)
            if not record or record.status.is_terminal:
                return

            record.status = JobStatus.COMPLETED
            record.progress = 100
            record.current_stage = "Completed"
            record.completed_at = datetime.now(timezone.utc)
            record.result = result
            self._cleanup_temp_file(record.file_path)

            duration_ms = 0.0
            if record.started_at and record.completed_at:
                duration_ms = round((record.completed_at - record.started_at).total_seconds() * 1000.0, 2)

            metrics_registry.record_job_completed(duration_ms)
            log_event(
                "analysis.job.completed",
                job_id=job_id,
                request_id=record.request_id,
                duration_ms=duration_ms,
                status=JobStatus.COMPLETED.value,
            )

    def fail_job(
        self,
        job_id: str,
        code: str,
        message: str,
    ) -> None:
        """Transitions job to FAILED state with sanitized error payload."""
        with self._lock:
            record = self._jobs.get(job_id)
            if not record or record.status.is_terminal:
                return

            record.status = JobStatus.FAILED
            # Do NOT report 100 on failure
            if record.progress >= 100:
                record.progress = 99
            record.current_stage = "Failed"
            record.completed_at = datetime.now(timezone.utc)
            record.error = JobError(code=code, message=message)
            self._cleanup_temp_file(record.file_path)

            duration_ms = 0.0
            if record.started_at and record.completed_at:
                duration_ms = round((record.completed_at - record.started_at).total_seconds() * 1000.0, 2)

            metrics_registry.record_job_failed(code)
            log_event(
                "analysis.job.failed",
                level=logging.ERROR,
                job_id=job_id,
                request_id=record.request_id,
                error_code=code,
                duration_ms=duration_ms,
                status=JobStatus.FAILED.value,
            )

    def _worker_execute(self, job_id: str) -> None:
        """
        Background worker thread executing unified DSP pipeline for a job.
        """
        with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return

            # If cancelled while waiting in thread pool queue
            if record.status == JobStatus.CANCELLED or record.cancel_requested:
                record.status = JobStatus.CANCELLED
                record.current_stage = "Cancelled"
                record.completed_at = datetime.now(timezone.utc)
                self._cleanup_temp_file(record.file_path)
                metrics_registry.record_job_cancelled()
                log_event(
                    "analysis.job.cancelled",
                    job_id=job_id,
                    request_id=record.request_id,
                    status=JobStatus.CANCELLED.value,
                    stage="Cancelled",
                )
                return

            record.status = JobStatus.PROCESSING
            record.started_at = datetime.now(timezone.utc)
            record.current_stage = "Audio preprocessing"
            record.progress = 5
            file_path = record.file_path
            original_filename = record.original_filename
            req_id = record.request_id

        log_event(
            "analysis.job.started",
            job_id=job_id,
            request_id=req_id,
            status=JobStatus.PROCESSING.value,
        )

        if not file_path or not os.path.exists(file_path):
            self.fail_job(
                job_id=job_id,
                code="FILE_NOT_FOUND",
                message="Temporary audio file could not be located on disk.",
            )
            return

        def progress_cb(prog: int, stage_name: str) -> None:
            self.update_progress(job_id, prog, stage_name)
            log_event(
                "analysis.job.stage_started",
                job_id=job_id,
                request_id=req_id,
                stage=stage_name,
                progress=prog,
            )

        def cancellation_chk() -> bool:
            with self._lock:
                rec = self._jobs.get(job_id)
                return bool(rec and (rec.cancel_requested or rec.status == JobStatus.CANCELLED))

        try:
            # Check initial cancellation
            if cancellation_chk():
                raise JobCancelledException()

            # Execute pipeline
            dsp_result: UnifiedAnalysisResult = self._pipeline.process_file(
                file_path=file_path,
                progress_callback=progress_cb,
                cancellation_check=cancellation_chk,
            )

            # Record stage timings into record and metrics registry
            with self._lock:
                rec = self._jobs.get(job_id)
                if rec:
                    rec.stage_timings = dict(dsp_result.stage_timings_ms)

            for stage_name, stage_dur in dsp_result.stage_timings_ms.items():
                metrics_registry.record_stage_duration(stage_name, stage_dur)
                log_event(
                    "analysis.job.stage_completed",
                    job_id=job_id,
                    request_id=req_id,
                    stage=stage_name,
                    duration_ms=stage_dur,
                )

            # Check if cancellation was observed right before finalizing
            if cancellation_chk():
                raise JobCancelledException()

            # Format final response
            response = format_analysis_response(
                analysis_id=job_id,
                result=dsp_result,
                filename=original_filename,
            )

            self.complete_job(job_id, response)

        except JobCancelledException:
            with self._lock:
                rec = self._jobs.get(job_id)
                if rec:
                    rec.status = JobStatus.CANCELLED
                    rec.current_stage = "Cancelled"
                    rec.completed_at = datetime.now(timezone.utc)
                    self._cleanup_temp_file(rec.file_path)
            metrics_registry.record_job_cancelled()
            log_event(
                "analysis.job.cancelled",
                job_id=job_id,
                request_id=req_id,
                status=JobStatus.CANCELLED.value,
                stage="Cancelled",
            )

        except AudioTooLongError as e:
            self.fail_job(
                job_id=job_id,
                code="DURATION_EXCEEDED",
                message=str(e),
            )
        except (InvalidAudioError, AudioPreprocessingError) as e:
            self.fail_job(
                job_id=job_id,
                code="INVALID_AUDIO_FORMAT",
                message=str(e),
            )
        except Exception as e:
            logger.exception(f"Unhandled worker error during analysis job {job_id}: {type(e).__name__}")
            # Sanitize message - never leak file paths, secrets, or internal tracebacks
            sanitized_msg = "An error occurred during audio feature extraction and musical analysis."
            self.fail_job(
                job_id=job_id,
                code="PROCESSING_ERROR",
                message=sanitized_msg,
            )
        finally:
            self._cleanup_temp_file(file_path)

    @staticmethod
    def _cleanup_temp_file(file_path: Optional[str]) -> None:
        """Safely removes temporary audio file from disk."""
        if file_path:
            try:
                p = Path(file_path)
                if p.exists() and p.is_file():
                    p.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp audio file {file_path}: {e}")

    def _cleanup_expired_jobs_locked(self) -> None:
        """Purges completed/failed/cancelled jobs whose retention TTL has expired."""
        now = datetime.now(timezone.utc)
        expired_ids: List[str] = []
        for j_id, rec in self._jobs.items():
            if rec.status.is_terminal and rec.completed_at:
                age_seconds = (now - rec.completed_at).total_seconds()
                if age_seconds > self._job_retention_seconds:
                    expired_ids.append(j_id)

        for j_id in expired_ids:
            rec = self._jobs.pop(j_id, None)
            if rec:
                self._cleanup_temp_file(rec.file_path)

    def _evict_oldest_terminal_job_locked(self) -> None:
        """Evicts the oldest terminal job if max_retained_jobs limit is reached."""
        terminal_jobs = [
            (j_id, rec)
            for j_id, rec in self._jobs.items()
            if rec.status.is_terminal
        ]
        if terminal_jobs:
            # Sort by completed_at or created_at ascending (oldest first)
            terminal_jobs.sort(key=lambda item: item[1].completed_at or item[1].created_at)
            oldest_id, oldest_rec = terminal_jobs[0]
            self._jobs.pop(oldest_id, None)
            self._cleanup_temp_file(oldest_rec.file_path)

    def shutdown(self, wait: bool = False) -> None:
        """Safely shuts down the executor."""
        with self._lock:
            self._is_shutdown = True
            # Cancel any queued jobs
            for rec in self._jobs.values():
                if rec.status == JobStatus.QUEUED:
                    rec.status = JobStatus.CANCELLED
                    rec.current_stage = "Cancelled"
                    rec.completed_at = datetime.now(timezone.utc)
                    self._cleanup_temp_file(rec.file_path)
                elif rec.status == JobStatus.PROCESSING:
                    rec.cancel_requested = True

        self._executor.shutdown(wait=wait, cancel_futures=True)


# Global singleton instance
job_manager = JobManager()
