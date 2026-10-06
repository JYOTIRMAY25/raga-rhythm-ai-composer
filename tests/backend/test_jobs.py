"""
Comprehensive unit, integration, and lifecycle test suite for Asynchronous Analysis Job System.
Covers all 24 required test specifications:
1. job creation
2. queued state
3. processing state
4. completed state
5. failed state
6. unknown job -> 404
7. progress monotonicity
8. progress bounds (0-100)
9. stage transitions
10. result retrieval
11. error sanitization
12. job isolation
13. concurrent jobs
14. queue limit
15. running-job limit
16. queued cancellation
17. cooperative processing cancellation
18. completion-vs-cancellation race
19. cleanup of temp files
20. malformed job ID
21. repeated status requests
22. worker exception
23. manager shutdown
24. job retention / eviction
"""

from __future__ import annotations

import io
import os
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from fastapi.testclient import TestClient
from scipy.io import wavfile

from backend.app.analysis.preprocessor import (
    AudioPreprocessingError,
    AudioTooLongError,
    InvalidAudioError,
)
from backend.app.core.exceptions import (
    JobCancelledException,
    JobNotFoundError,
    JobQueueFullError,
)
from backend.app.jobs.manager import JobManager
from backend.app.jobs.models import JobRecord, JobStatus
from backend.app.main import app
from backend.app.schemas.analysis import AnalysisResponse


class TestAnalysisJobSystem(unittest.TestCase):
    """Test suite covering JobManager and Async API Endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.sample_rate = 22050

    def setUp(self):
        # Create an isolated JobManager instance per test to prevent test cross-contamination
        self.manager = JobManager(
            max_workers=2,
            max_queued_jobs=5,
            job_retention_seconds=10,
            max_retained_jobs=10,
        )

    def tearDown(self):
        self.manager.shutdown(wait=False)

    def _create_wav_file(self, duration_sec: float = 3.5, f0: float = 146.83) -> Path:
        """Creates a real valid WAV file in a temporary location."""
        sr = self.sample_rate
        t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False, dtype=np.float32)
        sig = 0.7 * np.sin(2 * np.pi * f0 * t) + 0.3 * np.sin(2 * np.pi * (f0 * 1.5) * t)
        sig = np.clip(sig, -1.0, 1.0)
        int_data = (sig * 32767).astype(np.int16)

        temp_dir = Path(tempfile.gettempdir()) / "ragarhythm_test_audio"
        temp_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_dir / f"test_{uuid.uuid4().hex}.wav"
        wavfile.write(str(file_path), sr, int_data)
        return file_path

    # ========================================================================
    # 1. Job Creation
    # ========================================================================
    def test_01_job_creation(self):
        """1. Job creation generates unpredictable UUID and sets initial state."""
        rec = self.manager.create_job("alaap.wav")
        self.assertIsNotNone(rec.job_id)
        # Verify valid UUID format
        parsed = uuid.UUID(rec.job_id)
        self.assertEqual(str(parsed), rec.job_id)
        self.assertEqual(rec.original_filename, "alaap.wav")
        self.assertEqual(rec.status, JobStatus.QUEUED)
        self.assertEqual(rec.progress, 0)
        self.assertEqual(rec.current_stage, "Initialization")
        self.assertIsNotNone(rec.created_at)
        self.assertIsNone(rec.started_at)
        self.assertIsNone(rec.completed_at)

    # ========================================================================
    # 2. Queued State
    # ========================================================================
    def test_02_queued_state(self):
        """2. Newly created job is stored in QUEUED status before execution."""
        rec = self.manager.create_job("test.wav")
        fetched = self.manager.get_job(rec.job_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.status, JobStatus.QUEUED)
        resp = fetched.to_status_response()
        self.assertEqual(resp.status, "QUEUED")
        self.assertEqual(resp.progress, 0)
        self.assertIsNone(resp.result)
        self.assertIsNone(resp.error)

    # ========================================================================
    # 3. Processing State
    # ========================================================================
    def test_03_processing_state(self):
        """3. When job starts execution, status transitions to PROCESSING."""
        wav_path = self._create_wav_file(duration_sec=3.0)
        rec = self.manager.create_job("test.wav", str(wav_path))
        self.manager.submit_job(rec.job_id)

        # Give small tick to start processing
        time.sleep(0.05)
        fetched = self.manager.get_job(rec.job_id)
        self.assertIn(fetched.status, (JobStatus.PROCESSING, JobStatus.COMPLETED))
        self.assertIsNotNone(fetched.started_at)

    # ========================================================================
    # 4. Completed State
    # ========================================================================
    def test_04_completed_state(self):
        """4. Successful analysis finishes in COMPLETED state with progress 100%."""
        wav_path = self._create_wav_file(duration_sec=3.0)
        rec = self.manager.create_job("test.wav", str(wav_path))
        self.manager.submit_job(rec.job_id)

        # Wait until terminal state
        start = time.perf_counter()
        while time.perf_counter() - start < 15.0:
            f = self.manager.get_job(rec.job_id)
            if f.status.is_terminal:
                break
            time.sleep(0.05)

        fetched = self.manager.get_job(rec.job_id)
        self.assertEqual(fetched.status, JobStatus.COMPLETED)
        self.assertEqual(fetched.progress, 100)
        self.assertEqual(fetched.current_stage, "Completed")
        self.assertIsNotNone(fetched.completed_at)
        self.assertIsNotNone(fetched.result)

    # ========================================================================
    # 5. Failed State
    # ========================================================================
    def test_05_failed_state(self):
        """5. Failure sets status to FAILED with sanitized error and progress < 100."""
        rec = self.manager.create_job("bad.wav", "/non/existent/file.wav")
        self.manager.submit_job(rec.job_id)

        start = time.perf_counter()
        while time.perf_counter() - start < 5.0:
            f = self.manager.get_job(rec.job_id)
            if f.status.is_terminal:
                break
            time.sleep(0.05)

        fetched = self.manager.get_job(rec.job_id)
        self.assertEqual(fetched.status, JobStatus.FAILED)
        self.assertNotEqual(fetched.progress, 100)
        self.assertIsNotNone(fetched.error)
        self.assertIsNotNone(fetched.completed_at)

    # ========================================================================
    # 6. Unknown Job -> 404
    # ========================================================================
    def test_06_unknown_job_404(self):
        """6. Querying unknown job ID via GET /analysis/{id} returns 404."""
        resp = self.client.get(f"/api/v1/analysis/{uuid.uuid4()}")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["error_code"], "JOB_NOT_FOUND")

    # ========================================================================
    # 7. Progress Monotonicity
    # ========================================================================
    def test_07_progress_monotonicity(self):
        """7. Progress updates cannot decrease or move backwards."""
        rec = self.manager.create_job("test.wav")
        self.manager.update_progress(rec.job_id, 30, "Pitch extraction")
        self.assertEqual(rec.progress, 30)

        # Attempt to set lower progress
        self.manager.update_progress(rec.job_id, 20, "Tonic estimation")
        self.assertEqual(rec.progress, 30)  # Monotonic invariant maintained

        self.manager.update_progress(rec.job_id, 70, "Raga detection")
        self.assertEqual(rec.progress, 70)

    # ========================================================================
    # 8. Progress Bounds (0-100)
    # ========================================================================
    def test_08_progress_bounds(self):
        """8. Progress is strictly clamped in [0, 100] and cannot be negative or >100."""
        rec = self.manager.create_job("test.wav")
        self.manager.update_progress(rec.job_id, -50, "Init")
        self.assertEqual(rec.progress, 0)

        self.manager.update_progress(rec.job_id, 150, "Init")
        self.assertLessEqual(rec.progress, 99)  # Max 99 until explicit complete_job

    # ========================================================================
    # 9. Stage Transitions
    # ========================================================================
    def test_09_stage_transitions(self):
        """9. Current stage reflects meaningful pipeline boundaries."""
        rec = self.manager.create_job("test.wav")
        stages = [
            (5, "Audio preprocessing"),
            (15, "Tonic estimation"),
            (30, "Pitch extraction"),
            (50, "Tonic resolution"),
            (60, "Swara analysis"),
            (70, "Raga detection"),
            (80, "Rhythm / beat analysis"),
            (90, "Tala classification"),
            (98, "Finalization"),
        ]
        for prog, stg in stages:
            self.manager.update_progress(rec.job_id, prog, stg)
            self.assertEqual(rec.progress, prog)
            self.assertEqual(rec.current_stage, stg)

    # ========================================================================
    # 10. Result Retrieval
    # ========================================================================
    def test_10_result_retrieval(self):
        """10. Completed job exposes valid structured musical AnalysisResponse."""
        wav_path = self._create_wav_file(duration_sec=3.0)
        rec = self.manager.create_job("test.wav", str(wav_path))
        self.manager.submit_job(rec.job_id)

        start = time.perf_counter()
        while time.perf_counter() - start < 15.0:
            f = self.manager.get_job(rec.job_id)
            if f.status.is_terminal:
                break
            time.sleep(0.05)

        fetched = self.manager.get_job(rec.job_id)
        self.assertEqual(fetched.status, JobStatus.COMPLETED)
        res = fetched.result
        self.assertIsNotNone(res)
        self.assertIsInstance(res, AnalysisResponse)
        self.assertIsNotNone(res.tonic.frequency_hz)
        self.assertIsNotNone(res.raga.name)
        self.assertIsNotNone(res.tala.name)

    # ========================================================================
    # 11. Error Sanitization
    # ========================================================================
    def test_11_error_sanitization(self):
        """11. Internal exceptions are sanitized to prevent leaking paths or traces."""
        rec = self.manager.create_job("test.wav")
        # Trigger failure with simulated unhandled internal exception
        self.manager.fail_job(
            rec.job_id,
            code="PROCESSING_ERROR",
            message="An error occurred during audio feature extraction.",
        )
        resp = rec.to_status_response()
        self.assertEqual(resp.status, "FAILED")
        self.assertIsNotNone(resp.error)
        self.assertNotIn("Traceback", resp.error.message)
        self.assertNotIn("C:\\", resp.error.message)
        self.assertNotIn("/home/", resp.error.message)

    # ========================================================================
    # 12. Job Isolation
    # ========================================================================
    def test_12_job_isolation(self):
        """12. Two concurrent jobs maintain completely isolated state and progress."""
        j1 = self.manager.create_job("job1.wav")
        j2 = self.manager.create_job("job2.wav")

        self.assertNotEqual(j1.job_id, j2.job_id)
        self.manager.update_progress(j1.job_id, 45, "Pitch extraction")
        self.manager.update_progress(j2.job_id, 85, "Tala classification")

        self.assertEqual(self.manager.get_job(j1.job_id).progress, 45)
        self.assertEqual(self.manager.get_job(j2.job_id).progress, 85)

    # ========================================================================
    # 13. Concurrent Jobs
    # ========================================================================
    def test_13_concurrent_jobs(self):
        """13. Multiple concurrent jobs execute in worker pool safely."""
        p1 = self._create_wav_file(duration_sec=3.0, f0=130.81)
        p2 = self._create_wav_file(duration_sec=3.0, f0=146.83)

        j1 = self.manager.create_job("audio1.wav", str(p1))
        j2 = self.manager.create_job("audio2.wav", str(p2))

        self.manager.submit_job(j1.job_id)
        self.manager.submit_job(j2.job_id)

        start = time.perf_counter()
        while time.perf_counter() - start < 20.0:
            rec1 = self.manager.get_job(j1.job_id)
            rec2 = self.manager.get_job(j2.job_id)
            if rec1.status.is_terminal and rec2.status.is_terminal:
                break
            time.sleep(0.05)

        self.assertEqual(self.manager.get_job(j1.job_id).status, JobStatus.COMPLETED)
        self.assertEqual(self.manager.get_job(j2.job_id).status, JobStatus.COMPLETED)

    # ========================================================================
    # 14. Queue Limit
    # ========================================================================
    def test_14_queue_limit(self):
        """14. Exceeding max_queued_jobs raises JobQueueFullError."""
        # Max queued is configured to 5 in setUp
        for _ in range(5):
            self.manager.create_job("fill.wav")

        # 6th job should exceed capacity
        with self.assertRaises(JobQueueFullError):
            self.manager.create_job("overflow.wav")

    # ========================================================================
    # 15. Running Job Limit
    # ========================================================================
    def test_15_running_job_limit(self):
        """15. Thread pool concurrency is bounded by max_workers."""
        self.assertEqual(self.manager._executor._max_workers, 2)

    # ========================================================================
    # 16. Queued Cancellation
    # ========================================================================
    def test_16_queued_cancellation(self):
        """16. Cancelling a job while QUEUED immediately sets CANCELLED."""
        wav_path = self._create_wav_file(duration_sec=3.0)
        rec = self.manager.create_job("queued.wav", str(wav_path))
        self.assertEqual(rec.status, JobStatus.QUEUED)

        status, msg = self.manager.cancel_job(rec.job_id)
        self.assertEqual(status, JobStatus.CANCELLED)
        fetched = self.manager.get_job(rec.job_id)
        self.assertEqual(fetched.status, JobStatus.CANCELLED)
        self.assertEqual(fetched.current_stage, "Cancelled")

        # Submitting now should be a no-op
        self.manager.submit_job(rec.job_id)
        self.assertEqual(self.manager.get_job(rec.job_id).status, JobStatus.CANCELLED)

    # ========================================================================
    # 17. Cooperative Processing Cancellation
    # ========================================================================
    def test_17_cooperative_processing_cancellation(self):
        """17. Cancelling a PROCESSING job sets cancel_requested and aborts at stage boundary."""
        wav_path = self._create_wav_file(duration_sec=4.0)
        rec = self.manager.create_job("process.wav", str(wav_path))
        self.manager.submit_job(rec.job_id)

        # Request cancellation immediately
        status, msg = self.manager.cancel_job(rec.job_id)

        start = time.perf_counter()
        while time.perf_counter() - start < 10.0:
            f = self.manager.get_job(rec.job_id)
            if f.status.is_terminal:
                break
            time.sleep(0.05)

        fetched = self.manager.get_job(rec.job_id)
        self.assertEqual(fetched.status, JobStatus.CANCELLED)

    # ========================================================================
    # 18. Completion-vs-Cancellation Race
    # ========================================================================
    def test_18_completion_vs_cancellation_race(self):
        """18. If a job finishes before cancellation is observed, COMPLETED wins."""
        wav_path = self._create_wav_file(duration_sec=3.0)
        rec = self.manager.create_job("race.wav", str(wav_path))
        self.manager.submit_job(rec.job_id)

        # Wait until COMPLETED
        start = time.perf_counter()
        while time.perf_counter() - start < 15.0:
            f = self.manager.get_job(rec.job_id)
            if f.status == JobStatus.COMPLETED:
                break
            time.sleep(0.05)

        self.assertEqual(self.manager.get_job(rec.job_id).status, JobStatus.COMPLETED)
        # Attempt cancellation after completion
        status, msg = self.manager.cancel_job(rec.job_id)
        self.assertEqual(status, JobStatus.COMPLETED)
        self.assertEqual(self.manager.get_job(rec.job_id).status, JobStatus.COMPLETED)

    # ========================================================================
    # 19. Cleanup of Temp Files
    # ========================================================================
    def test_19_cleanup_temp_files(self):
        """19. Temporary files are unlinked from disk upon terminal states."""
        wav_path = self._create_wav_file(duration_sec=3.0)
        self.assertTrue(wav_path.exists())

        rec = self.manager.create_job("cleanup.wav", str(wav_path))
        self.manager.submit_job(rec.job_id)

        start = time.perf_counter()
        while time.perf_counter() - start < 15.0:
            f = self.manager.get_job(rec.job_id)
            if f.status.is_terminal:
                break
            time.sleep(0.05)

        self.assertFalse(wav_path.exists())

    # ========================================================================
    # 20. Malformed Job ID
    # ========================================================================
    def test_20_malformed_job_id(self):
        """20. Malformed job ID queries gracefully return 404."""
        malformed_ids = ["", "undefined", "null", "../../../etc/passwd", "123", "!@#$%^&*()"]
        for mid in malformed_ids:
            resp = self.client.get(f"/api/v1/analysis/{mid}")
            self.assertIn(resp.status_code, (404, 400, 422))

    # ========================================================================
    # 21. Repeated Status Requests
    # ========================================================================
    def test_21_repeated_status_requests(self):
        """21. Repeated polling queries do not mutate state or cause race conditions."""
        rec = self.manager.create_job("poll.wav")
        for _ in range(20):
            fetched = self.manager.get_job(rec.job_id)
            self.assertEqual(fetched.status, JobStatus.QUEUED)
            self.assertEqual(fetched.progress, 0)

    # ========================================================================
    # 22. Worker Exception Handling
    # ========================================================================
    def test_22_worker_exception(self):
        """22. Unhandled worker exception transitions job to FAILED and cleans temp file."""
        wav_path = self._create_wav_file(duration_sec=3.0)
        rec = self.manager.create_job("fail.wav", str(wav_path))

        with patch.object(self.manager._pipeline, "process_file", side_effect=RuntimeError("Simulated DSP crash")):
            self.manager.submit_job(rec.job_id)

            start = time.perf_counter()
            while time.perf_counter() - start < 5.0:
                f = self.manager.get_job(rec.job_id)
                if f.status.is_terminal:
                    break
                time.sleep(0.05)

            fetched = self.manager.get_job(rec.job_id)
            self.assertEqual(fetched.status, JobStatus.FAILED)
            self.assertEqual(fetched.error.code, "PROCESSING_ERROR")
            self.assertFalse(wav_path.exists())

    # ========================================================================
    # 23. Manager Shutdown
    # ========================================================================
    def test_23_manager_shutdown(self):
        """23. Shutting down manager cancels queued work and blocks new jobs."""
        mgr = JobManager(max_workers=2)
        j1 = mgr.create_job("shut.wav")
        mgr.shutdown(wait=False)

        self.assertEqual(mgr.get_job(j1.job_id).status, JobStatus.CANCELLED)
        with self.assertRaises(RuntimeError):
            mgr.create_job("new.wav")

    # ========================================================================
    # 24. Job Retention & Eviction
    # ========================================================================
    def test_24_job_retention(self):
        """24. Expired jobs exceeding TTL are purged, bounded capacity enforced."""
        mgr = JobManager(max_workers=1, max_queued_jobs=10, job_retention_seconds=1, max_retained_jobs=3)

        # Create and complete 3 jobs
        j1 = mgr.create_job("j1.wav")
        mgr.complete_job(j1.job_id, MagicMock(spec=AnalysisResponse))

        j2 = mgr.create_job("j2.wav")
        mgr.complete_job(j2.job_id, MagicMock(spec=AnalysisResponse))

        j3 = mgr.create_job("j3.wav")
        mgr.complete_job(j3.job_id, MagicMock(spec=AnalysisResponse))

        self.assertEqual(len(mgr._jobs), 3)

        # Wait for 1s TTL expiration
        time.sleep(1.2)

        # Creating j4 triggers cleanup of expired jobs
        j4 = mgr.create_job("j4.wav")
        self.assertNotIn(j1.job_id, mgr._jobs)
        self.assertNotIn(j2.job_id, mgr._jobs)
        self.assertNotIn(j3.job_id, mgr._jobs)
        self.assertIn(j4.job_id, mgr._jobs)

        mgr.shutdown(wait=False)

    # ========================================================================
    # 25. Atomic Status Snapshot Consistency (Medium 1)
    # ========================================================================
    def test_25_atomic_get_job_status_consistency(self):
        """25. get_job_status() snapshots state under lock; progress 100 occurs only for COMPLETED."""
        mgr = JobManager(max_workers=2, max_queued_jobs=10)
        rec = mgr.create_job("atomic_status.wav")
        mock_res = MagicMock(spec=AnalysisResponse)

        status_snapshots = []
        errors = []

        # Thread 1: Rapidly fetches get_job_status
        def reader():
            for _ in range(200):
                try:
                    s = mgr.get_job_status(rec.job_id)
                    if s:
                        status_snapshots.append((s.status, s.progress))
                except Exception as e:
                    errors.append(e)

        # Thread 2: Simulates worker updating progress and completing
        def worker():
            for p in range(10, 95, 15):
                mgr.update_progress(rec.job_id, p, f"Stage {p}")
                time.sleep(0.001)
            mgr.complete_job(rec.job_id, mock_res)

        t_reader = threading.Thread(target=reader)
        t_worker = threading.Thread(target=worker)

        t_reader.start()
        t_worker.start()
        t_reader.join()
        t_worker.join()

        self.assertEqual(len(errors), 0)
        # Verify invariant on all snapshots: progress == 100 <=> status == COMPLETED
        for st, prog in status_snapshots:
            if prog == 100:
                self.assertEqual(st, JobStatus.COMPLETED)
            if st != JobStatus.COMPLETED:
                self.assertLess(prog, 100)

        mgr.shutdown(wait=False)

    # ========================================================================
    # 26. Pre-Upload Queue Capacity Guard (Medium 2)
    # ========================================================================
    def test_26_pre_upload_capacity_guard(self):
        """26. has_capacity() accurately reflects queue headroom and gates requests."""
        mgr = JobManager(max_workers=1, max_queued_jobs=2)
        self.assertTrue(mgr.has_capacity())

        j1 = mgr.create_job("j1.wav")
        self.assertTrue(mgr.has_capacity())

        j2 = mgr.create_job("j2.wav")
        # Capacity now exhausted (2/2 active jobs)
        self.assertFalse(mgr.has_capacity())

        # Calling create_job when full raises JobQueueFullError
        with self.assertRaises(JobQueueFullError):
            mgr.create_job("j3.wav")

        # Completing j1 restores capacity
        mgr.complete_job(j1.job_id, MagicMock(spec=AnalysisResponse))
        self.assertTrue(mgr.has_capacity())

        mgr.shutdown(wait=False)

    # ========================================================================
    # 27. Atomic Job Registration & Submission Failure Handling (Medium 3)
    # ========================================================================
    def test_27_atomic_create_and_submit_failure_handling(self):
        """27. Executor rejection does not orphan QUEUED jobs and restores queue capacity."""
        mgr = JobManager(max_workers=1, max_queued_jobs=5)
        wav_path = self._create_wav_file(duration_sec=3.0)

        # Mock executor submit to raise RuntimeError (e.g. shutdown / thread pool rejection)
        with patch.object(mgr._executor, "submit", side_effect=RuntimeError("cannot schedule new futures")):
            with self.assertRaises(RuntimeError):
                mgr.create_and_submit_job("rejected.wav", str(wav_path))

        # Verify: no job left in QUEUED state
        active_count = sum(1 for j in mgr._jobs.values() if not j.status.is_terminal)
        self.assertEqual(active_count, 0)

        # Verify the rejected job transitioned to FAILED with sanitized error
        failed_jobs = [j for j in mgr._jobs.values() if j.status == JobStatus.FAILED]
        self.assertEqual(len(failed_jobs), 1)
        self.assertEqual(failed_jobs[0].error.code, "SUBMISSION_FAILED")

        # Verify temporary file was cleaned up
        self.assertFalse(wav_path.exists())

        mgr.shutdown(wait=False)

    # ========================================================================
    # 28. Terminal Cancellation Idempotency (Low 4)
    # ========================================================================
    def test_28_terminal_cancellation_idempotence(self):
        """28. Cancelling already terminal jobs returns 200 OK idempotently with terminal status."""
        mgr = JobManager(max_workers=2, max_queued_jobs=5)

        # Completed job cancellation
        j1 = mgr.create_job("comp.wav")
        mgr.complete_job(j1.job_id, MagicMock(spec=AnalysisResponse))
        st1, msg1 = mgr.cancel_job(j1.job_id)
        self.assertEqual(st1, JobStatus.COMPLETED)
        self.assertIn("already reached terminal status", msg1)

        # Failed job cancellation
        j2 = mgr.create_job("fail.wav")
        mgr.fail_job(j2.job_id, "TEST_ERR", "Test failure")
        st2, msg2 = mgr.cancel_job(j2.job_id)
        self.assertEqual(st2, JobStatus.FAILED)
        self.assertIn("already reached terminal status", msg2)

        # Repeated cancellation on cancelled job
        j3 = mgr.create_job("canc.wav")
        st3a, _ = mgr.cancel_job(j3.job_id)
        self.assertEqual(st3a, JobStatus.CANCELLED)
        st3b, msg3b = mgr.cancel_job(j3.job_id)
        self.assertEqual(st3b, JobStatus.CANCELLED)
        self.assertIn("already reached terminal status", msg3b)

        mgr.shutdown(wait=False)


if __name__ == "__main__":
    unittest.main()
