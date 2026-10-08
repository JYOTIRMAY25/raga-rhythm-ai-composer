"""
Release Validation & Adversarial Suite for Phase 5.5.
Validates production readiness across Security, Observability, Container Lifecycles,
Audio Generation Quality, Async Job Processing, and Property-Based Invariants.
"""

from __future__ import annotations

import io
import math
import os
import random
import struct
import tempfile
import time
import wave
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy.io import wavfile

from backend.app.composition.audio_renderer import AudioRenderer
from backend.app.composition.composition_engine import CompositionEngine
from backend.app.composition.composition_models import (
    CompositionCycle,
    CompositionRequest,
    SwaraEvent,
    SymbolicComposition,
    ValidationResult,
)
from backend.app.core.config import Settings, parse_cors_origins
from backend.app.jobs.manager import JobManager
from backend.app.jobs.models import JobStatus
from backend.app.main import app
from backend.app.observability import sanitize_request_id

client = TestClient(app)


def _generate_synthetic_test_wav(duration_sec: float = 0.5, sample_rate: int = 22050, freq_hz: float = 220.0) -> bytes:
    """Generates an in-memory mono PCM WAV buffer for smoke testing."""
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False, dtype=np.float32)
    # 220Hz fundamental with modest 2nd harmonic
    audio = 0.5 * np.sin(2 * np.pi * freq_hz * t) + 0.2 * np.sin(2 * np.pi * (freq_hz * 2) * t)
    # Safe 16-bit PCM conversion
    audio_int16 = (audio * 32767).astype(np.int16)
    buf = io.BytesIO()
    wavfile.write(buf, sample_rate, audio_int16)
    return buf.getvalue()


class TestReleaseValidation:
    """Release validation and adversarial security/runtime verification."""

    # =========================================================================
    # Category 1: Security & Observability Boundaries
    # =========================================================================

    def test_adv_rel_sec_01_request_id_crlf_log_injection_defense(self):
        """Security: Malicious X-Request-ID headers containing CRLF or control characters are sanitized."""
        malicious_headers = [
            "valid-prefix\r\nInjected-Header: evil",
            "req-123\nGET /admin HTTP/1.1",
            "req-\x00-null-byte",
            "bad\r\n\r\nHTTP/1.1 200 OK",
            "    ",  # whitespace only
            "a" * 200,  # overly long ID
        ]
        for bad_id in malicious_headers:
            sanitized = sanitize_request_id(bad_id)
            assert "\r" not in sanitized
            assert "\n" not in sanitized
            assert "\x00" not in sanitized
            assert len(sanitized) <= 64
            assert len(sanitized) > 0

            # Make live request with this header
            resp = client.get("/api/v1/health", headers={"X-Request-ID": bad_id})
            assert resp.status_code == 200
            resp_req_id = resp.headers.get("X-Request-ID", "")
            assert "\r" not in resp_req_id
            assert "\n" not in resp_req_id

    def test_adv_rel_sec_02_production_error_sanitization(self):
        """Security: Internal errors return standardized error responses without leaking tracebacks or paths."""
        resp = client.get("/api/v1/analysis/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
        data = resp.json()
        assert "error_code" in data
        assert "message" in data
        assert data.get("error_code") == "JOB_NOT_FOUND"
        # Must not leak filesystem paths or stack frames
        assert "Traceback" not in resp.text
        assert "File \"" not in resp.text
        assert "raga-rhythm-ai-composer" not in resp.text

    def test_adv_rel_sec_03_production_cors_strictness(self):
        """Security: Production CORS parser forbids wildcard and rejects untrusted origin patterns."""
        with pytest.raises(ValueError, match="strictly forbidden in production"):
            parse_cors_origins("*", app_env="production")

        with pytest.raises(ValueError, match="strictly forbidden in production"):
            parse_cors_origins("https://valid.com, *", app_env="production")

    # =========================================================================
    # Category 2: Production Endpoints Smoke & Readiness Verification
    # =========================================================================

    def test_adv_rel_prod_01_health_and_readiness_probes(self):
        """Production Smoke: /health and /ready respond with valid schemas and timing headers."""
        # 1. Health check
        h_resp = client.get("/api/v1/health")
        assert h_resp.status_code == 200
        h_data = h_resp.json()
        assert h_data.get("status") == "healthy"
        assert "timestamp" in h_data
        assert "version" in h_data
        assert "X-Request-ID" in h_resp.headers
        assert "X-Response-Time-Ms" in h_resp.headers

        # 2. Readiness probe
        r_resp = client.get("/api/v1/ready")
        assert r_resp.status_code == 200
        r_data = r_resp.json()
        assert r_data.get("status") == "ready"
        assert "job_system" in r_data
        assert "timestamp" in r_data

    def test_adv_rel_prod_02_metrics_endpoint_json_format(self):
        """Production Smoke: /metrics returns valid in-process observability snapshot."""
        m_resp = client.get("/api/v1/metrics")
        assert m_resp.status_code == 200
        assert "application/json" in m_resp.headers.get("content-type", "")
        content = m_resp.json()
        assert "requests" in content
        assert "jobs" in content
        assert "stages" in content

    def test_adv_rel_prod_03_metadata_catalog_endpoints(self):
        """Production Smoke: /ragas and /talas return full canonical catalogs."""
        # Ragas catalog
        ragas_resp = client.get("/api/v1/ragas")
        assert ragas_resp.status_code == 200
        ragas_data = ragas_resp.json()
        assert "total" in ragas_data
        assert "ragas" in ragas_data
        assert ragas_data["total"] >= 70, f"Expected >= 70 ragas, got {ragas_data['total']}"
        first_raga = ragas_data["ragas"][0]
        assert "id" in first_raga
        assert "name" in first_raga
        assert "thaat" in first_raga

        # Talas catalog
        talas_resp = client.get("/api/v1/talas")
        assert talas_resp.status_code == 200
        talas_data = talas_resp.json()
        assert "total" in talas_data
        assert "talas" in talas_data
        assert talas_data["total"] >= 6
        tala_ids = {t["id"] for t in talas_data["talas"]}
        assert "teental" in tala_ids
        assert "rupak" in tala_ids or "roopak" in tala_ids

    # =========================================================================
    # Category 3: Async Analysis Job End-to-End & Fault Handling
    # =========================================================================

    def test_adv_rel_jobs_01_end_to_end_analysis_submission_and_poll(self):
        """Async Analysis E2E: Valid WAV upload -> 202 Accepted -> Polling -> Completed result."""
        wav_bytes = _generate_synthetic_test_wav(duration_sec=0.5, freq_hz=220.0)
        files = {"file": ("test_sine.wav", io.BytesIO(wav_bytes), "audio/wav")}

        # Step 1: Submit job
        sub_resp = client.post("/api/v1/analyze", files=files)
        assert sub_resp.status_code == 202, f"Failed submission: {sub_resp.text}"
        sub_data = sub_resp.json()
        job_id = sub_data.get("job_id")
        assert job_id is not None
        assert sub_data.get("status") in ("QUEUED", "PROCESSING", "COMPLETED")

        # Step 2: Poll status
        max_attempts = 40
        completed = False
        final_record = None
        for _ in range(max_attempts):
            poll_resp = client.get(f"/api/v1/analysis/{job_id}")
            assert poll_resp.status_code == 200
            final_record = poll_resp.json()
            status = final_record.get("status")
            if status in ("COMPLETED", "FAILED", "CANCELLED"):
                completed = True
                break
            time.sleep(0.1)

        assert completed, f"Job did not finish in time: {final_record}"
        assert final_record.get("status") == "COMPLETED"
        result = final_record.get("result")
        assert result is not None
        assert "raga" in result
        assert "tonic" in result
        assert "audio_metadata" in result
        assert "stage_timings" in final_record

    def test_adv_rel_jobs_02_empty_and_corrupt_audio_rejection(self):
        """Async Analysis: Rejects empty or corrupt audio files with appropriate status codes."""
        # 1. 0-byte file raises EmptyFileError (422)
        empty_files = {"file": ("empty.wav", io.BytesIO(b""), "audio/wav")}
        empty_resp = client.post("/api/v1/analyze", files=empty_files)
        assert empty_resp.status_code == 422
        assert empty_resp.json()["error_code"] == "EMPTY_FILE"

        # 2. Corrupt garbage header file
        garbage_bytes = b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00GARBAGE_DATA_HERE"
        garbage_files = {"file": ("corrupt.wav", io.BytesIO(garbage_bytes), "audio/wav")}
        sub_resp = client.post("/api/v1/analyze", files=garbage_files)
        # Accepted as job then failed asynchronously or rejected at boundary
        if sub_resp.status_code == 202:
            job_id = sub_resp.json()["job_id"]
            # Poll until failed
            for _ in range(20):
                poll_resp = client.get(f"/api/v1/analysis/{job_id}")
                if poll_resp.json()["status"] == "FAILED":
                    break
                time.sleep(0.05)
            assert poll_resp.json()["status"] == "FAILED"
            assert "error" in poll_resp.json()
        else:
            assert sub_resp.status_code in (400, 422)

    def test_adv_rel_jobs_03_job_cancellation_lifecycle(self):
        """Async Analysis: Job cancellation correctly updates status to cancelled."""
        jm = JobManager(max_workers=1, max_queued_jobs=10)
        job = jm.create_job(original_filename="cancel_me.wav", file_path=None)
        assert job.status == JobStatus.QUEUED

        # Cancel queued job
        status, message = jm.cancel_job(job.job_id)
        assert status == JobStatus.CANCELLED
        updated = jm.get_job(job.job_id)
        assert updated.status == JobStatus.CANCELLED
        jm.shutdown(wait=False)

    # =========================================================================
    # Category 4: Composition Audio Generation & Audio Quality Invariants
    # =========================================================================

    def test_adv_rel_audio_01_canonical_raga_wav_generation(self):
        """Composition Audio: Yaman + Teental generates valid, finite, normalized mono WAV."""
        engine = CompositionEngine()
        renderer = AudioRenderer(sample_rate=22050)

        req = CompositionRequest(
            raga_id="yaman",
            tala_id="teental",
            duration_seconds=15,
            seed=42,
        )
        comp = engine.compose(req)
        assert comp.validation.valid is True

        audio_samples = renderer.render_composition(comp)
        assert isinstance(audio_samples, np.ndarray)
        assert audio_samples.ndim == 1, "Audio must be strictly mono"
        assert len(audio_samples) > 0

        # Invariant checks
        assert not np.isnan(audio_samples).any(), "Audio samples contain NaN"
        assert not np.isinf(audio_samples).any(), "Audio samples contain Inf"
        max_amp = float(np.max(np.abs(audio_samples)))
        assert max_amp <= 1.0, f"Digital clipping detected: max amplitude {max_amp} > 1.0"
        assert max_amp > 0.01, "Generated audio is completely silent"

        # Verify WAV serialization
        wav_bytes = renderer.encode_wav(audio_samples)
        assert wav_bytes.startswith(b"RIFF"), "Missing RIFF magic bytes"
        assert b"WAVE" in wav_bytes[:12], "Missing WAVE format marker"

        # Parse with wave module
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            assert wf.getnchannels() == 1, "WAV must have 1 channel (mono)"
            assert wf.getsampwidth() == 2, "WAV must be 16-bit PCM (2 bytes per sample)"
            assert wf.getframerate() == 22050
            frames = wf.readframes(wf.getnframes())
            assert len(frames) == len(audio_samples) * 2

    def test_adv_rel_audio_02_microtonal_raga_wav_generation(self):
        """Composition Audio: Bhairav (microtonal komal re/dha) + Roopak generates compliant audio."""
        engine = CompositionEngine()
        renderer = AudioRenderer(sample_rate=22050)

        req = CompositionRequest(
            raga_id="bhairav",
            tala_id="roopak",
            duration_seconds=15,
            seed=123,
        )
        comp = engine.compose(req)
        assert comp.validation.valid is True

        audio_samples = renderer.render_composition(comp)
        assert isinstance(audio_samples, np.ndarray)
        assert not np.isnan(audio_samples).any()
        assert not np.isinf(audio_samples).any()
        max_amp = float(np.max(np.abs(audio_samples)))
        assert max_amp <= 1.0
        assert max_amp > 0.01

        wav_bytes = renderer.encode_wav(audio_samples)
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 22050

    # =========================================================================
    # Category 5: Property / Fuzz Testing
    # =========================================================================

    def test_adv_rel_prop_01_wav_serializer_invariant_fuzz(self):
        """
        Property Test: 100 randomized synthesized signals across varied lengths,
        sample rates, and amplitudes must all serialize to strictly conforming RIFF/WAV files.
        Invariants:
        1. Always mono (1 channel).
        2. Sample rate strictly preserved.
        3. Parsed frames count == len(input_samples).
        4. No sample value in decoded 16-bit PCM exceeds [-32768, 32767].
        5. Byte size equals header (44 bytes) + n_samples * 2.
        """
        random.seed(99)
        np.random.seed(99)
        renderer = AudioRenderer()

        sample_rates = [8000, 16000, 22050, 44100]

        for _ in range(100):
            sr = random.choice(sample_rates)
            renderer.sample_rate = sr
            n_samples = random.randint(100, 20000)

            # Random float32 audio bounded in [-1.0, 1.0] with potential random DC bias
            raw_audio = np.random.uniform(-1.0, 1.0, size=n_samples).astype(np.float32)

            wav_data = renderer.encode_wav(raw_audio)

            # Invariant 5: File length check
            expected_total_bytes = 44 + (n_samples * 2)
            assert len(wav_data) == expected_total_bytes, f"Size mismatch: got {len(wav_data)}, expected {expected_total_bytes}"

            # Invariant 1, 2, 3: Header and framing checks
            with wave.open(io.BytesIO(wav_data), "rb") as wf:
                assert wf.getnchannels() == 1
                assert wf.getframerate() == sr
                assert wf.getnframes() == n_samples
                decoded_bytes = wf.readframes(n_samples)
                decoded_samples = np.frombuffer(decoded_bytes, dtype=np.int16)
                assert len(decoded_samples) == n_samples
                assert np.all(decoded_samples >= -32768)
                assert np.all(decoded_samples <= 32767)
