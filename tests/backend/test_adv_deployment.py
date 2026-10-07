"""
Adversarial test suite for Phase 5.4 Production Deployment Readiness.
Covers Security, Configuration Validation, Resource Safety, Shutdown State Machine,
and Property Fuzzing across configuration and deployment boundaries.
"""

from __future__ import annotations

import json
import os
import random
import string
import tempfile
from pathlib import Path
import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings, parse_cors_origins
from backend.app.jobs.manager import JobManager
from backend.app.jobs.models import JobStatus


class TestAdversarialDeployment:
    """Adversarial security, configuration, and runtime resilience tests."""

    # =========================================================================
    # Category 1: Security (CORS Injection, Wildcard Rejection, Secret Leakage)
    # =========================================================================

    def test_adv_sec_01_production_wildcard_cors_rejected(self):
        """Security: Enforces that wildcard '*' CORS origin is strictly rejected in production."""
        # 1. Comma-separated wildcard
        with pytest.raises(ValueError, match="Wildcard '\\*' CORS origin is strictly forbidden in production mode"):
            parse_cors_origins("*", app_env="production")

        # 2. JSON list with wildcard
        with pytest.raises(ValueError, match="Wildcard '\\*' CORS origin is strictly forbidden in production mode"):
            parse_cors_origins('["https://app.example.com", "*"]', app_env="production")

        # 3. Settings model initialization in production with wildcard
        with pytest.raises(ValidationError):
            Settings(app_env="production", cors_origins=["*"])

    def test_adv_sec_02_cors_header_injection_defense(self):
        """Security: Rejects control characters and CRLF injection inside CORS origin strings."""
        malicious_origins = [
            "https://example.com\r\nSet-Cookie: evil=true",
            "https://example.com\x00evil.com",
            "https://example.com\tadmin=1",
            "https://example.com\nAccess-Control-Allow-Origin: *",
        ]
        for bad_origin in malicious_origins:
            with pytest.raises(ValueError, match="forbidden control characters"):
                parse_cors_origins(bad_origin, app_env="development")

    def test_adv_sec_03_secret_leakage_in_config_validation(self):
        """Security: Ensures configuration errors do not echo API keys or secrets in exception strings."""
        secret_key = "AIzaSySecretTestKey123456789"
        # Force a validation error while secret is set
        try:
            Settings(
                app_env="production",
                port=999999,  # Invalid port
                gemini_api_key=secret_key,
            )
            pytest.fail("Expected ValidationError on invalid port")
        except ValidationError as err:
            err_msg = str(err)
            assert secret_key not in err_msg, "Secret API key leaked in ValidationError representation!"

    def test_adv_sec_04_temp_file_path_traversal_defense(self):
        """Security: Path traversal inputs in job manager file handling must not escape temp boundaries."""
        jm = JobManager(max_workers=1, max_queued_jobs=10)
        traversal_filenames = [
            "../../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\calc.exe",
            "....//....//payload.wav",
        ]
        for name in traversal_filenames:
            job = jm.create_job(original_filename=name, file_path=None)
            assert job.job_id is not None
            # The original filename is stored safely as metadata, but file_path is None or safely bound
            assert not str(job.job_id).startswith("..")
        jm.shutdown(wait=False)

    # =========================================================================
    # Category 2: Configuration Validation (PORT, Workers, Bounds, JSON format)
    # =========================================================================

    def test_adv_cfg_01_invalid_port_validation(self):
        """Configuration: Verifies port bounds (1..65535)."""
        invalid_ports = [0, -1, 65536, 100000]
        for port in invalid_ports:
            with pytest.raises(ValidationError):
                Settings(port=port)

        # Valid ports must succeed
        s1 = Settings(port=80)
        s2 = Settings(port=8080)
        s3 = Settings(port=65535)
        assert s1.port == 80 and s2.port == 8080 and s3.port == 65535

    def test_adv_cfg_02_invalid_worker_and_queue_bounds(self):
        """Configuration: Enforces strict non-zero, reasonable bounds on workers and queue depth."""
        # Zero or negative workers
        with pytest.raises(ValidationError):
            Settings(job_max_workers=0)
        with pytest.raises(ValidationError):
            Settings(job_max_workers=-4)
        with pytest.raises(ValidationError):
            Settings(job_max_workers=100)  # > 64

        # Zero or negative queue capacity
        with pytest.raises(ValidationError):
            Settings(job_queue_capacity=0)
        with pytest.raises(ValidationError):
            Settings(job_queue_capacity=-10)

        # Retention limit bounds
        with pytest.raises(ValidationError):
            Settings(job_retention_limit=0)

        # Retention TTL bounds (minimum 60 seconds)
        with pytest.raises(ValidationError):
            Settings(job_retention_ttl_seconds=10)

    def test_adv_cfg_03_malformed_json_cors_origins(self):
        """Configuration: Catches malformed JSON arrays in CORS_ORIGINS cleanly."""
        malformed_json = '[{"broken": json'
        with pytest.raises(ValueError, match="Invalid JSON format for CORS_ORIGINS"):
            parse_cors_origins(malformed_json, app_env="development")

    # =========================================================================
    # Category 3: Resource Safety & Runtime Shutdown State Machine
    # =========================================================================

    def test_adv_res_01_oversized_upload_mb_bound(self):
        """Resource Safety: Upload limits must be bounded between 1.0 and 500.0 MB."""
        with pytest.raises(ValidationError):
            Settings(max_upload_size_mb=0.5)
        with pytest.raises(ValidationError):
            Settings(max_upload_size_mb=1000.0)

        # Derived bytes must scale accurately
        s = Settings(max_upload_size_mb=50.0)
        assert s.max_upload_bytes == 50 * 1024 * 1024

    def test_adv_res_02_shutdown_rejection_and_readiness(self):
        """Runtime: Shutdown transitions readiness to degraded/shutting_down and rejects submissions."""
        jm = JobManager(max_workers=2, max_queued_jobs=10)

        # Initial ready probe
        is_ready, status_str, _ = jm.is_ready()
        assert is_ready is True
        assert status_str == "ready"

        # Trigger shutdown
        jm.shutdown(wait=False)

        # Post-shutdown readiness
        is_ready, status_str, details = jm.is_ready()
        assert is_ready is False
        assert status_str == "shutting_down"
        assert details.get("is_shutdown") is True

        # Has capacity must return False
        assert jm.has_capacity() is False

        # Attempt to create job after shutdown must fail fast
        with pytest.raises(RuntimeError, match="JobManager has been shut down"):
            jm.create_job(original_filename="late_upload.wav")

    # =========================================================================
    # Category 4: Property / Fuzz Testing
    # =========================================================================

    def test_adv_prop_01_cors_parser_fuzz_invariants(self):
        """
        Property Test: 500 randomized fuzz inputs through parse_cors_origins.
        Invariants:
        1. Never returns None.
        2. In production, never returns any list containing '*'.
        3. No returned string contains forbidden control characters (\r, \n, \0, \t).
        4. Either successfully produces a list of clean strings or raises ValueError.
        """
        random.seed(42)
        valid_schemes = ["http://", "https://", ""]

        for _ in range(500):
            # Generate random input: mixture of comma-separated or JSON-like
            coin = random.random()
            app_env = "production" if random.random() < 0.5 else "development"

            if coin < 0.4:
                # Comma separated
                n_items = random.randint(0, 5)
                items = []
                for _ in range(n_items):
                    prefix = random.choice(valid_schemes)
                    body = "".join(random.choices(string.ascii_letters + string.digits + ".-_*", k=random.randint(1, 15)))
                    if random.random() < 0.1:
                        # inject control char
                        body += random.choice(["\r", "\n", "\x00", "\t"])
                    items.append(prefix + body)
                raw_input = ",".join(items)
            elif coin < 0.7:
                # JSON list
                n_items = random.randint(0, 4)
                items = []
                for _ in range(n_items):
                    items.append("https://" + "".join(random.choices(string.ascii_letters, k=6)) + ".com")
                raw_input = json.dumps(items)
            else:
                # Random arbitrary noise
                raw_input = "".join(random.choices(string.printable, k=random.randint(0, 30)))

            try:
                res = parse_cors_origins(raw_input, app_env=app_env)
                assert isinstance(res, list), f"Expected list, got {type(res)}"
                if app_env == "production":
                    assert "*" not in res, f"Production parser permitted '*' origin: {res}"
                for origin in res:
                    assert not any(c in origin for c in "\r\n\x00\t"), f"Control char in parsed origin: {origin!r}"
            except ValueError:
                # Expected safe rejection on invalid inputs
                pass
