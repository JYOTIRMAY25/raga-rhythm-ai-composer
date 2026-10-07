"""
Comprehensive test suite for Phase 5.3 Production Observability & Reliability.
Covers:
1. Request ID generation and sanitization
2. X-Request-ID response headers
3. Valid client request IDs
4. Malicious request IDs rejection/replacement
5. Concurrent request ID isolation
6. Request -> job correlation
7. Job lifecycle events logging
8. Failure logging
9. Cancellation logging
10. Stage timings presence in jobs and pipeline
11. Stage timings non-negative
12. Monotonic clock timing behavior
13. Metrics counters tracking
14. Metrics gauges tracking
15. Concurrent metrics updates thread safety
16. Queue metrics accuracy
17. Worker metrics accuracy
18. Liveness probe (GET /api/v1/health)
19. Readiness probe (GET /api/v1/ready)
20. Readiness under shutdown
21. Readiness under queue saturation
22. Metrics endpoint privacy (GET /api/v1/metrics)
23. Error taxonomy consistency
24. Logging failure isolation (pipeline resilient)
25. Metrics failure isolation (pipeline resilient)
26. No secrets in logs
27. No server paths in public responses
28. No high-cardinality dimensions in aggregate metrics
29. Malformed correlation headers
30. Repeated polling does not distort lifecycle counters
"""

from __future__ import annotations

import concurrent.futures
import io
import json
import logging
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from scipy.io import wavfile

from backend.app.core.config import settings
from backend.app.core.exceptions import AudioValidationError, JobQueueFullError
from backend.app.jobs import JobManager, JobStatus, job_manager
from backend.app.main import app
from backend.app.observability import (
    StageTimer,
    get_current_request_id,
    log_event,
    metrics_registry,
    reset_current_request_id,
    sanitize_request_id,
    set_current_request_id,
)


class TestObservabilitySuite(unittest.TestCase):
    """Production observability and reliability test suite."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.sample_rate = 22050

    def setUp(self):
        metrics_registry.reset()

    def _create_wav_bytes(self, duration_sec: float = 3.5, f0: float = 146.83) -> bytes:
        """Generates valid WAV audio bytes in memory."""
        sr = self.sample_rate
        t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False, dtype=np.float32)
        sig = 0.6 * np.sin(2 * np.pi * f0 * t) + 0.3 * np.sin(2 * np.pi * (f0 * 1.5) * t)

        beat_interval = int(sr * 0.5)
        for b in range(0, len(sig), beat_interval):
            decay = np.exp(-np.linspace(0, 10, min(1000, len(sig) - b)))
            sig[b : b + len(decay)] += 0.5 * decay

        sig = np.clip(sig / np.max(np.abs(sig)) * 0.85, -1.0, 1.0)
        int_data = (sig * 32767).astype(np.int16)

        bio = io.BytesIO()
        wavfile.write(bio, sr, int_data)
        bio.seek(0)
        return bio.read()

    # 1. request ID generated
    def test_01_request_id_generated_when_absent(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        req_id = response.headers.get("X-Request-ID")
        self.assertIsNotNone(req_id)
        self.assertGreater(len(req_id), 10)

    # 2. request ID response header
    def test_02_request_id_response_header_present(self):
        response = self.client.get("/api/v1/ready")
        self.assertIn("X-Request-ID", response.headers)
        self.assertIn("X-Response-Time-Ms", response.headers)

    # 3. safe valid incoming request ID behavior
    def test_03_valid_incoming_request_id_preserved(self):
        custom_id = "trace-client-12345-abc_XYZ"
        response = self.client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Request-ID"), custom_id)

    # 4. malicious request ID rejected/sanitized
    def test_04_malicious_request_id_sanitized(self):
        # Newline injection attempt
        malicious_id = "req-1\r\nX-Injected-Header: evil\n[CRITICAL] hack"
        response = self.client.get("/api/v1/health", headers={"X-Request-ID": malicious_id})
        self.assertEqual(response.status_code, 200)
        returned_id = response.headers.get("X-Request-ID")
        self.assertNotEqual(returned_id, malicious_id)
        self.assertNotIn("\r", returned_id)
        self.assertNotIn("\n", returned_id)
        self.assertNotIn("evil", returned_id)

    # 5. concurrent request ID isolation
    def test_05_concurrent_request_id_isolation(self):
        def make_call(idx: int):
            cid = f"client-req-{idx:04d}"
            res = self.client.get("/api/v1/health", headers={"X-Request-ID": cid})
            return res.headers.get("X-Request-ID") == cid

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(make_call, range(30)))
        self.assertTrue(all(results))

    # 6. request -> job correlation
    def test_06_request_to_job_correlation(self):
        custom_req_id = "req-corr-job-test-777"
        wav_bytes = self._create_wav_bytes(duration_sec=3.5)
        files = {"file": ("corr_audio.wav", wav_bytes, "audio/wav")}

        res = self.client.post("/api/v1/analyze", files=files, headers={"X-Request-ID": custom_req_id})
        self.assertEqual(res.status_code, 202)
        data = res.json()
        job_id = data["job_id"]

        # Check job record preserves request ID
        record = job_manager.get_job(job_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.request_id, custom_req_id)

        # Polling status response also reflects request_id
        poll_res = self.client.get(f"/api/v1/analysis/{job_id}")
        self.assertEqual(poll_res.status_code, 200)
        self.assertEqual(poll_res.json()["request_id"], custom_req_id)

    # 7. lifecycle logging
    def test_07_job_lifecycle_logging(self):
        events_logged = []

        class TestHandler(logging.Handler):
            def emit(self, record):
                ev = getattr(record, "event", None)
                if ev:
                    events_logged.append(ev)

        th = TestHandler()
        th.setLevel(logging.INFO)
        lg = logging.getLogger("ragarhythm")
        lg.setLevel(logging.INFO)
        lg.addHandler(th)
        try:
            wav_bytes = self._create_wav_bytes(duration_sec=3.5)
            files = {"file": ("life_audio.wav", wav_bytes, "audio/wav")}
            res = self.client.post("/api/v1/analyze", files=files)
            self.assertEqual(res.status_code, 202)
            self.assertIn("analysis.job.created", events_logged)
            self.assertIn("analysis.job.queued", events_logged)
        finally:
            lg.removeHandler(th)

    # 8. failure logging
    def test_08_failure_logging(self):
        events_logged = []

        class TestHandler(logging.Handler):
            def emit(self, record):
                ev = getattr(record, "event", None)
                if ev:
                    events_logged.append(ev)

        th = TestHandler()
        th.setLevel(logging.INFO)
        lg = logging.getLogger("ragarhythm")
        lg.setLevel(logging.INFO)
        lg.addHandler(th)
        try:
            # Upload empty file to trigger failure
            files = {"file": ("empty.wav", b"", "audio/wav")}
            res = self.client.post("/api/v1/analyze", files=files)
            self.assertEqual(res.status_code, 422)
            self.assertIn("request.failed", events_logged)
        finally:
            lg.removeHandler(th)

    # 9. cancellation logging
    def test_09_cancellation_logging(self):
        rec = job_manager.create_job("to_cancel.wav")
        new_status, msg = job_manager.cancel_job(rec.job_id)
        self.assertEqual(new_status, JobStatus.CANCELLED)
        snap = metrics_registry.get_snapshot()
        self.assertGreaterEqual(snap["jobs"]["cancelled_total"], 1)

    # 10. stage timings present
    def test_10_stage_timings_present(self):
        timer = StageTimer()
        timer.start_stage("preprocessing")
        time.sleep(0.01)
        dur = timer.stop_stage("preprocessing")
        self.assertGreater(dur, 0.0)
        timings = timer.to_dict()
        self.assertIn("preprocessing", timings)

    # 11. timings non-negative
    def test_11_timings_non_negative(self):
        timer = StageTimer()
        timer.record_duration("test_stage", -50.0)
        self.assertGreaterEqual(timer.get_duration("test_stage"), 0.0)

    # 12. monotonic timing behavior
    def test_12_monotonic_timing_behavior(self):
        timer = StageTimer()
        timer.start_stage("tonic_estimation")
        t0 = time.perf_counter()
        time.sleep(0.02)
        elapsed = timer.stop_stage("tonic_estimation")
        t1 = time.perf_counter()
        expected_ms = (t1 - t0) * 1000.0
        # Should be within tight margin of actual perf_counter delta
        self.assertAlmostEqual(elapsed, expected_ms, delta=10.0)

    # 13. metrics counters
    def test_13_metrics_counters(self):
        metrics_registry.reset()
        metrics_registry.record_request(15.2, is_error=False)
        metrics_registry.record_request(25.4, is_error=True)
        metrics_registry.record_job_created()
        metrics_registry.record_job_completed(500.0)
        metrics_registry.record_job_failed("INVALID_AUDIO_FORMAT")
        metrics_registry.record_job_cancelled()

        snap = metrics_registry.get_snapshot()
        self.assertEqual(snap["requests"]["total"], 2)
        self.assertEqual(snap["requests"]["failed"], 1)
        self.assertEqual(snap["jobs"]["created_total"], 1)
        self.assertEqual(snap["jobs"]["completed_total"], 1)
        self.assertEqual(snap["jobs"]["failed_total"], 1)
        self.assertEqual(snap["jobs"]["cancelled_total"], 1)
        self.assertEqual(snap["failures"]["INVALID_AUDIO_FORMAT"], 1)

    # 14. metrics gauges
    def test_14_metrics_gauges(self):
        snap = metrics_registry.get_snapshot()
        self.assertIn("capacity", snap["workers"])
        self.assertIn("capacity", snap["queue"])
        self.assertIn("available", snap["queue"])
        self.assertGreaterEqual(snap["workers"]["capacity"], 1)

    # 15. concurrent metrics updates
    def test_15_concurrent_metrics_updates(self):
        metrics_registry.reset()

        def worker_fn():
            for _ in range(100):
                metrics_registry.record_request(5.0)
                metrics_registry.record_stage_duration("pitch_extraction", 2.0)

        threads = [threading.Thread(target=worker_fn) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        snap = metrics_registry.get_snapshot()
        self.assertEqual(snap["requests"]["total"], 1000)
        self.assertEqual(snap["stages"]["pitch_extraction"]["count"], 1000)

    # 16. queue metrics
    def test_16_queue_metrics(self):
        snap = metrics_registry.get_snapshot()
        self.assertIn("capacity", snap["queue"])
        self.assertIn("available", snap["queue"])
        self.assertLessEqual(snap["queue"]["available"], snap["queue"]["capacity"])

    # 17. worker metrics
    def test_17_worker_metrics(self):
        snap = metrics_registry.get_snapshot()
        self.assertIn("capacity", snap["workers"])
        self.assertIn("active", snap["workers"])
        self.assertLessEqual(snap["workers"]["active"], snap["workers"]["capacity"])

    # 18. liveness endpoint
    def test_18_liveness_endpoint(self):
        res = self.client.get("/api/v1/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("version", data)

    # 19. readiness endpoint
    def test_19_readiness_endpoint(self):
        res = self.client.get("/api/v1/ready")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn(data["status"], ["ready", "degraded"])
        self.assertIn("job_system", data)

    # 20. readiness during shutdown
    def test_20_readiness_during_shutdown(self):
        test_mgr = JobManager(max_workers=2, max_queued_jobs=5)
        test_mgr.shutdown(wait=False)
        is_ready, status_str, details = test_mgr.is_ready()
        self.assertFalse(is_ready)
        self.assertEqual(status_str, "shutting_down")

    # 21. readiness under queue saturation
    def test_21_readiness_under_queue_saturation(self):
        test_mgr = JobManager(max_workers=2, max_queued_jobs=1)
        test_mgr.create_job("job1.wav")
        is_ready, status_str, details = test_mgr.is_ready()
        self.assertTrue(is_ready)
        self.assertEqual(status_str, "degraded")
        self.assertEqual(details["queue_available"], 0)

    # 22. metrics endpoint privacy
    def test_22_metrics_endpoint_privacy(self):
        res = self.client.get("/api/v1/metrics")
        self.assertEqual(res.status_code, 200)
        text = res.text
        # Ensure no passwords, keys, or private filesystem paths leaked
        self.assertNotIn("secret", text.lower())
        self.assertNotIn("token", text.lower())
        self.assertNotIn("c:\\", text.lower())
        self.assertNotIn("/home/", text.lower())

    # 23. error taxonomy
    def test_23_error_taxonomy(self):
        # Invalid format
        files = {"file": ("bad.exe", b"MZ...", "application/x-dosexec")}
        res = self.client.post("/api/v1/analyze", files=files)
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertEqual(data["error_code"], "INVALID_AUDIO_FORMAT")

    # 24. logging failure does not fail analysis
    def test_24_logging_failure_isolation(self):
        with patch("backend.app.observability.logging.logger.log", side_effect=RuntimeError("Logging failed!")):
            # Logging failure should not cause log_event to raise
            try:
                log_event("test.event", key="value")
            except Exception as e:
                self.fail(f"log_event raised exception: {e}")

    # 25. metrics failure does not fail analysis
    def test_25_metrics_failure_isolation(self):
        with patch.object(metrics_registry, "record_job_created", side_effect=RuntimeError("Metrics broke!")):
            # create_job should still complete successfully
            rec = job_manager.create_job("metrics_fail_safe.wav")
            self.assertIsNotNone(rec.job_id)

    # 26. no secrets in logs
    def test_26_no_secrets_in_logs(self):
        logged_records = []

        class TestHandler(logging.Handler):
            def emit(self, record):
                logged_records.append(record)

        th = TestHandler()
        logging.getLogger("ragarhythm").addHandler(th)
        try:
            log_event("secret.test", api_key="SUPER_SECRET_123", authorization="Bearer xyz")
            for rec in logged_records:
                self.assertNotIn("SUPER_SECRET_123", str(rec.__dict__))
                self.assertNotIn("Bearer xyz", str(rec.__dict__))
        finally:
            logging.getLogger("ragarhythm").removeHandler(th)

    # 27. no server paths in public responses
    def test_27_no_server_paths_in_public_responses(self):
        res = self.client.get("/api/v1/analysis/nonexistent-job-uuid-123")
        self.assertEqual(res.status_code, 404)
        body = res.text
        self.assertNotIn("backend/app", body)
        self.assertNotIn("C:\\", body)

    # 28. no high-cardinality job/request IDs in aggregate metrics
    def test_28_no_high_cardinality_in_aggregate_metrics(self):
        metrics_registry.record_job_failed("JOB_NOT_FOUND")
        snap = metrics_registry.get_snapshot()
        # Failures dimension only contains safe taxonomy codes
        for code in snap["failures"]:
            self.assertIn(code, ["JOB_NOT_FOUND", "INTERNAL_ERROR", "SUBMISSION_FAILED", "DURATION_EXCEEDED", "INVALID_AUDIO_FORMAT", "PROCESSING_ERROR"])
            # Ensure no UUID4 formatted keys in failures
            self.assertFalse("-" in code and len(code) == 36)

    # 29. malformed correlation headers
    def test_29_malformed_correlation_headers(self):
        dirty_ids = [
            "id\x00with_null",
            "id\x1b[31mwith_ansi",
            "id with spaces and symbols!@#$",
            "a" * 200,  # Oversized (200 chars)
        ]
        for dirty in dirty_ids:
            res = self.client.get("/api/v1/health", headers={"X-Request-ID": dirty})
            clean_res = res.headers.get("X-Request-ID")
            self.assertNotEqual(clean_res, dirty)
            self.assertLessEqual(len(clean_res), 64)

    # 30. repeated polling does not distort lifecycle counters
    def test_30_repeated_polling_does_not_distort_counters(self):
        metrics_registry.reset()
        rec = job_manager.create_job("poll_test.wav")
        initial_snap = metrics_registry.get_snapshot()
        created_count = initial_snap["jobs"]["created_total"]

        # Poll status 10 times
        for _ in range(10):
            self.client.get(f"/api/v1/analysis/{rec.job_id}")

        after_snap = metrics_registry.get_snapshot()
        self.assertEqual(after_snap["jobs"]["created_total"], created_count)


if __name__ == "__main__":
    unittest.main()
