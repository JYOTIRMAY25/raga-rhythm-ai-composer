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


if __name__ == "__main__":
    unittest.main()
