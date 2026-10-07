"""
Adversarial test suite for Phase 5.3 Production Observability & Reliability.
Attacks system with malicious headers, concurrency races, resource limits, and property fuzzing.
Designed from specification invariants.
"""

from __future__ import annotations

import concurrent.futures
import random
import re
import string
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.jobs import JobManager, JobStatus
from backend.app.main import app
from backend.app.observability import (
    SAFE_REQUEST_ID_REGEX,
    metrics_registry,
    sanitize_request_id,
)


class TestAdversarialObservability(unittest.TestCase):
    """Adversarial security, concurrency, failure isolation, and fuzzing tests."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # =========================================================================
    # Category 1: Security & Log Injection Attacks
    # =========================================================================

    def test_adv_sec_01_crlf_log_and_header_splitting(self):
        """Attacks with HTTP header splitting / CRLF injection payloads."""
        crlf_payloads = [
            "req\r\nSet-Cookie: sessionId=attacker\r\n",
            "req-123\nInjected: True\n\nHTTP/1.1 200 OK",
            "id\rSet-Cookie: evil=1",
            "req\r\n\r\n<script>alert(1)</script>",
        ]
        for payload in crlf_payloads:
            res = self.client.get("/api/v1/health", headers={"X-Request-ID": payload})
            header_val = res.headers.get("X-Request-ID", "")
            # Ensure CRLF is stripped/rejected and never reflected
            self.assertNotIn("\r", header_val)
            self.assertNotIn("\n", header_val)
            self.assertNotIn("Set-Cookie", header_val)
            self.assertTrue(SAFE_REQUEST_ID_REGEX.match(header_val))

    def test_adv_sec_02_oversized_request_id_buffer_overflow_defense(self):
        """Attacks with extremely large request IDs (10,000 to 50,000 chars)."""
        huge_id = "A" * 15000
        res = self.client.get("/api/v1/health", headers={"X-Request-ID": huge_id})
        header_val = res.headers.get("X-Request-ID", "")
        # Must be bounded to max 64 characters
        self.assertLessEqual(len(header_val), 64)
        self.assertNotEqual(header_val, huge_id)
        self.assertTrue(SAFE_REQUEST_ID_REGEX.match(header_val))

    def test_adv_sec_03_null_byte_and_terminal_escape_injection(self):
        """Attacks with null bytes, ANSI terminal escapes, and non-printable control characters."""
        toxic_payloads = [
            "req\x00_bypass_root",
            "req\x1b[31;1mRED_ALERT\x1b[0m",
            "req\x07\x08\x0b\x0c",
            "req\x7f_del_char",
        ]
        for payload in toxic_payloads:
            res = self.client.get("/api/v1/health", headers={"X-Request-ID": payload})
            header_val = res.headers.get("X-Request-ID", "")
            self.assertNotIn("\x00", header_val)
            self.assertNotIn("\x1b", header_val)
            self.assertTrue(SAFE_REQUEST_ID_REGEX.match(header_val))

    # =========================================================================
    # Category 2: Concurrency & State Isolation
    # =========================================================================

    def test_adv_conc_01_multithreaded_request_id_isolation(self):
        """Concurrently fires 60 requests with unique client IDs to verify contextvar isolation."""
        def call_endpoint(idx: int):
            client_req_id = f"worker-corr-uuid-{idx:05d}"
            res = self.client.get("/api/v1/ready", headers={"X-Request-ID": client_req_id})
            received = res.headers.get("X-Request-ID")
            return received == client_req_id

        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            outcomes = list(executor.map(call_endpoint, range(60)))

        self.assertTrue(all(outcomes), "Concurrent request IDs experienced contextvar crosstalk!")

    def test_adv_conc_02_metrics_thread_safety_high_contention(self):
        """Spawns 20 threads simultaneously hammering the metrics collector under contention."""
        metrics_registry.reset()
        num_threads = 20
        ops_per_thread = 200

        def spam_metrics():
            for i in range(ops_per_thread):
                metrics_registry.record_request(duration_ms=float(i), is_error=(i % 5 == 0))
                metrics_registry.record_stage_duration("tonic_resolution", duration_ms=1.5)
                metrics_registry.record_job_created()

        threads = [threading.Thread(target=spam_metrics) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        snap = metrics_registry.get_snapshot()
        expected_total = num_threads * ops_per_thread
        self.assertEqual(snap["requests"]["total"], expected_total)
        self.assertEqual(snap["jobs"]["created_total"], expected_total)
        self.assertEqual(snap["stages"]["tonic_resolution"]["count"], expected_total)

    # =========================================================================
    # Category 3: Failure Isolation & Defensive Resilience
    # =========================================================================

    def test_adv_fail_01_logging_system_crash_isolation(self):
        """Simulates internal logger failure: job operations must not crash."""
        with patch("backend.app.observability.logging.logger.log", side_effect=Exception("Disk logger fatal!")):
            mgr = JobManager(max_workers=2, max_queued_jobs=5)
            # Should create job smoothly without propagating logger crash
            job = mgr.create_job("crash_proof.wav")
            self.assertIsNotNone(job.job_id)
            status, _ = mgr.cancel_job(job.job_id)
            self.assertEqual(status, JobStatus.CANCELLED)

    def test_adv_fail_02_metrics_system_crash_isolation(self):
        """Simulates metrics registry lock exception: core API and job handling continues."""
        with patch.object(metrics_registry, "record_request", side_effect=RuntimeError("Metrics down!")):
            res = self.client.get("/api/v1/health")
            self.assertEqual(res.status_code, 200)

    # =========================================================================
    # Category 4: Lifecycle, Shutdown & Queue Saturation Invariants
    # =========================================================================

    def test_adv_life_01_readiness_state_machine_under_shutdown(self):
        """Verifies readiness probe correctly transitions to HTTP 503 during shutdown."""
        mgr = JobManager(max_workers=2, max_queued_jobs=2)
        is_ready, status_str, _ = mgr.is_ready()
        self.assertTrue(is_ready)
        self.assertEqual(status_str, "ready")

        mgr.shutdown(wait=False)
        is_ready, status_str, details = mgr.is_ready()
        self.assertFalse(is_ready)
        self.assertEqual(status_str, "shutting_down")
        self.assertTrue(details.get("is_shutdown"))

    def test_adv_life_02_double_cancel_and_terminal_idempotence(self):
        """Verifies repeated cancellation does not corrupt metrics or state."""
        mgr = JobManager(max_workers=2, max_queued_jobs=5)
        rec = mgr.create_job("idempotent_cancel.wav")
        st1, _ = mgr.cancel_job(rec.job_id)
        self.assertEqual(st1, JobStatus.CANCELLED)

        # Repeated cancellation on terminal state
        st2, msg2 = mgr.cancel_job(rec.job_id)
        self.assertEqual(st2, JobStatus.CANCELLED)
        self.assertIn("already reached terminal status", msg2)

    # =========================================================================
    # Category 5: Property / Fuzz Testing
    # =========================================================================

    def test_adv_prop_01_fuzz_sanitize_request_id_invariants(self):
        """
        Property Test: For 500 arbitrary fuzzed inputs containing random unicode,
        null bytes, escapes, huge lengths, emojis, and symbols,
        sanitize_request_id ALWAYS returns a string satisfying SAFE_REQUEST_ID_REGEX
        with 1 <= len <= 64, and NEVER raises an unhandled exception.
        """
        random.seed(42)
        fuzz_corpus = [
            None,
            "",
            "   ",
            "\t\n\r",
            "valid-id_123",
            "a" * 64,
            "b" * 65,
            "c" * 1000,
            "\x00",
            "\x1b[31m",
            "select * from users;--",
            "<script>alert('xss')</script>",
            "../../etc/passwd",
            "🦀🎵🎶",
            "Привет_мир",
            "مرحبا",
        ]

        # Generate 500 randomized fuzz strings
        all_chars = string.printable + "".join(chr(i) for i in range(128, 256))
        for _ in range(500):
            length = random.randint(0, 200)
            fuzz_str = "".join(random.choice(all_chars) for _ in range(length))
            fuzz_corpus.append(fuzz_str)

        for raw_input in fuzz_corpus:
            try:
                result = sanitize_request_id(raw_input)
            except Exception as e:
                self.fail(f"sanitize_request_id raised unexpected exception on input {raw_input!r}: {e}")

            # INVARIANT 1: Result is non-empty string
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 0)

            # INVARIANT 2: Result length is strictly <= 64
            self.assertLessEqual(len(result), 64)

            # INVARIANT 3: Result matches SAFE_REQUEST_ID_REGEX strictly
            self.assertIsNotNone(
                SAFE_REQUEST_ID_REGEX.match(result),
                f"Sanitized result {result!r} failed SAFE_REQUEST_ID_REGEX on input {raw_input!r}",
            )


if __name__ == "__main__":
    unittest.main()
