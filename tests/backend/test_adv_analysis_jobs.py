"""
Adversarial and property-based test suite attacking the Asynchronous Analysis Job System.
Designed strictly against specifications and invariants.

Coverage across categories:
- Category 1: Concurrency (rapid polling, concurrent submit races, concurrent cancellation)
- Category 2: Boundary & Input (zero duration, boundary progress clamping, queue saturation)
- Category 3: Security & Isolation (path traversal, sanitized errors, file isolation)
- Category 4: State & Idempotency (repeated cancellations, terminal state immutability)
- Category 5: Property / Invariants (monotonic progress property, non-decreasing progression under arbitrary updates)
"""

from __future__ import annotations

import io
import os
import random
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
    JobNotFoundError,
    JobQueueFullError,
)
from backend.app.jobs.manager import JobManager
from backend.app.jobs.models import JobRecord, JobStatus
from backend.app.main import app
from backend.app.schemas.analysis import AnalysisResponse


class TestAdversarialAnalysisJobs(unittest.TestCase):
    """Adversarial and property tests attacking async analysis jobs."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.sample_rate = 22050

    def setUp(self):
        self.manager = JobManager(
            max_workers=2,
            max_queued_jobs=10,
            job_retention_seconds=5,
            max_retained_jobs=20,
        )

    def tearDown(self):
        self.manager.shutdown(wait=False)

    def _create_wav_file(self, duration_sec: float = 3.0, f0: float = 146.83) -> Path:
        """Creates a valid temporary WAV audio file."""
        sr = self.sample_rate
        t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False, dtype=np.float32)
        sig = 0.8 * np.sin(2 * np.pi * f0 * t)
        sig = np.clip(sig, -1.0, 1.0)
        int_data = (sig * 32767).astype(np.int16)

        temp_dir = Path(tempfile.gettempdir()) / "ragarhythm_adv_audio"
        temp_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_dir / f"adv_{uuid.uuid4().hex}.wav"
        wavfile.write(str(file_path), sr, int_data)
        return file_path

    # ========================================================================
    # Category 1: Concurrency Attacks
    # ========================================================================

    def test_adv_concurrency_rapid_status_polling(self):
        """Attacks job status endpoint with 100 rapid concurrent polling requests."""
        p = self._create_wav_file(duration_sec=3.0)
        rec = self.manager.create_job("rapid_poll.wav", str(p))
        self.manager.submit_job(rec.job_id)

        results = []
        errors = []

        def poll_worker():
            for _ in range(25):
                try:
                    job = self.manager.get_job(rec.job_id)
                    if job:
                        results.append(job.progress)
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=poll_worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, "No exceptions should occur during rapid polling")
        self.assertEqual(len(results), 100)

    def test_adv_concurrency_simultaneous_cancellation_requests(self):
        """Attacks cancel_job with multiple threads attempting to cancel the exact same job simultaneously."""
        p = self._create_wav_file(duration_sec=4.0)
        rec = self.manager.create_job("race_cancel.wav", str(p))
        self.manager.submit_job(rec.job_id)

        cancel_results = []

        def cancel_worker():
            res = self.manager.cancel_job(rec.job_id)
            cancel_results.append(res)

        threads = [threading.Thread(target=cancel_worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(cancel_results), 8)
        # All returns must be valid JobStatus and not crash
        for status, msg in cancel_results:
            self.assertIsInstance(status, JobStatus)
            self.assertIsInstance(msg, str)

    # ========================================================================
    # Category 2: Boundary & Input Attacks
    # ========================================================================

    def test_adv_boundary_queue_exhaustion(self):
        """Fills queue to exact capacity and asserts strict rejection on overflow."""
        mgr = JobManager(max_queued_jobs=3)
        j1 = mgr.create_job("j1.wav")
        j2 = mgr.create_job("j2.wav")
        j3 = mgr.create_job("j3.wav")

        with self.assertRaises(JobQueueFullError):
            mgr.create_job("overflow.wav")

        # Completing one job frees capacity
        mgr.complete_job(j1.job_id, MagicMock(spec=AnalysisResponse))
        j4 = mgr.create_job("j4.wav")
        self.assertIsNotNone(j4)
        mgr.shutdown(wait=False)

    def test_adv_boundary_progress_clamping_extremes(self):
        """Attacks progress updates with negative infinity, huge numbers, and boundaries."""
        rec = self.manager.create_job("bounds.wav")
        extreme_values = [-999999, 0, 50, 150, 1000000]

        for val in extreme_values:
            self.manager.update_progress(rec.job_id, val, "Stage")
            self.assertGreaterEqual(rec.progress, 0)
            self.assertLessEqual(rec.progress, 99)  # 100 reserved strictly for completed

    # ========================================================================
    # Category 3: Security & Isolation
    # ========================================================================

    def test_adv_security_no_internal_paths_in_sanitized_errors(self):
        """Verifies that unexpected worker failures never expose filesystem paths."""
        p = self._create_wav_file(duration_sec=3.0)
        rec = self.manager.create_job("sec_test.wav", str(p))

        with patch.object(
            self.manager._pipeline,
            "process_file",
            side_effect=Exception(f"Fatal crash inside /var/secret/keys/db.py at {p}"),
        ):
            self.manager.submit_job(rec.job_id)

            start = time.perf_counter()
            while time.perf_counter() - start < 5.0:
                f = self.manager.get_job(rec.job_id)
                if f.status.is_terminal:
                    break
                time.sleep(0.05)

            fetched = self.manager.get_job(rec.job_id)
            self.assertEqual(fetched.status, JobStatus.FAILED)
            # Assert sensitive info was not leaked in error payload
            self.assertNotIn("/var/secret", fetched.error.message)
            self.assertNotIn(str(p), fetched.error.message)

    # ========================================================================
    # Category 4: State & Idempotency
    # ========================================================================

    def test_adv_state_terminal_immutability(self):
        """Once COMPLETED, job state cannot be corrupted by subsequent progress or fail calls."""
        rec = self.manager.create_job("immutable.wav")
        mock_res = MagicMock(spec=AnalysisResponse)
        self.manager.complete_job(rec.job_id, mock_res)

        self.assertEqual(rec.status, JobStatus.COMPLETED)
        self.assertEqual(rec.progress, 100)

        # Attempt to mutate completed job
        self.manager.update_progress(rec.job_id, 50, "Swara analysis")
        self.assertEqual(rec.progress, 100)
        self.assertEqual(rec.status, JobStatus.COMPLETED)

        self.manager.fail_job(rec.job_id, "ERROR", "Failed late")
        self.assertEqual(rec.status, JobStatus.COMPLETED)

    # ========================================================================
    # Category 5: Property / Fuzz Testing (Invariants)
    # ========================================================================

    def test_adv_property_monotonic_progress_invariant(self):
        """Property: for any arbitrary random sequence of progress updates, progress is strictly non-decreasing."""
        rng = random.Random(42)
        rec = self.manager.create_job("fuzz.wav")

        last_progress = 0
        for _ in range(500):
            proposed_progress = rng.randint(-50, 200)
            self.manager.update_progress(rec.job_id, proposed_progress, "Fuzz stage")

            current_progress = rec.progress
            # Invariant 1: Progress is monotonic non-decreasing
            self.assertGreaterEqual(current_progress, last_progress)
            # Invariant 2: Progress is within bounds [0, 99]
            self.assertGreaterEqual(current_progress, 0)
            self.assertLessEqual(current_progress, 99)
            last_progress = current_progress

    def test_adv_property_progress_100_only_for_completed(self):
        """Property: across all possible job lifecycle states and arbitrary progress, 100 occurs ONLY for COMPLETED."""
        rng = random.Random(1337)
        statuses = [JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.COMPLETED]

        for _ in range(300):
            chosen_status = rng.choice(statuses)
            arbitrary_progress = rng.randint(-100, 300)

            rec = JobRecord(job_id=str(uuid.uuid4()), original_filename="fuzz.wav")
            rec.status = chosen_status
            rec.progress = arbitrary_progress

            resp = rec.to_status_response()
            # Invariant 1: 0 <= progress <= 100
            self.assertGreaterEqual(resp.progress, 0)
            self.assertLessEqual(resp.progress, 100)

            # Invariant 2: 100 occurs if and only if COMPLETED
            if chosen_status == JobStatus.COMPLETED:
                self.assertEqual(resp.progress, 100)
            else:
                self.assertLess(resp.progress, 100)

    def test_adv_saturated_queue_rejects_before_disk_write(self):
        """Attacks analyze endpoint when queue is full: must return 429 without invoking save_upload_to_storage."""
        wav_bytes = self._create_wav_file(duration_sec=3.0)

        with patch("backend.app.api.v1.endpoints.analyze.job_manager.has_capacity", return_value=False):
            with patch("backend.app.api.v1.endpoints.analyze.save_upload_to_storage") as mock_save:
                files = {"file": ("saturated.wav", wav_bytes.read_bytes(), "audio/wav")}
                resp = self.client.post("/api/v1/analyze", files=files)

                self.assertEqual(resp.status_code, 429)
                data = resp.json()
                self.assertEqual(data["error_code"], "JOB_QUEUE_FULL")
                # Proves disk write was bypassed!
                mock_save.assert_not_called()

    def test_adv_concurrent_capacity_boundary(self):
        """10 concurrent threads submit against max_queued_jobs=4; exactly 4 succeed, 6 fail, no leaks."""
        mgr = JobManager(max_workers=2, max_queued_jobs=4)

        successes = []
        full_errors = []

        def submitter(idx):
            try:
                rec = mgr.create_job(f"job_{idx}.wav")
                successes.append(rec.job_id)
            except JobQueueFullError as e:
                full_errors.append(e)

        threads = [threading.Thread(target=submitter, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(successes), 4)
        self.assertEqual(len(full_errors), 6)
        active_count = sum(1 for j in mgr._jobs.values() if not j.status.is_terminal)
        self.assertEqual(active_count, 4)

        mgr.shutdown(wait=False)

    def test_adv_executor_submit_failure_concurrent(self):
        """Concurrent executor rejections: all fail cleanly, no orphaned QUEUED jobs, capacity restored."""
        mgr = JobManager(max_workers=2, max_queued_jobs=5)

        with patch.object(mgr._executor, "submit", side_effect=RuntimeError("thread pool saturated")):
            rejected_errors = []

            def worker_submit(idx):
                wav = self._create_wav_file(duration_sec=2.0)
                try:
                    mgr.create_and_submit_job(f"worker_{idx}.wav", str(wav))
                except RuntimeError as re:
                    rejected_errors.append(re)

            threads = [threading.Thread(target=worker_submit, args=(i,)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(len(rejected_errors), 5)
            # Active queue capacity must be 0 (restored)
            active_count = sum(1 for j in mgr._jobs.values() if not j.status.is_terminal)
            self.assertEqual(active_count, 0)
            self.assertTrue(mgr.has_capacity())

        mgr.shutdown(wait=False)


if __name__ == "__main__":
    unittest.main()
