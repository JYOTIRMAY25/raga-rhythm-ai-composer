"""
Comprehensive integration and contract test suite for FastAPI REST API endpoints.
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from scipy.io import wavfile

from backend.app.main import app
from backend.app.core.config import settings


class TestAPIEndpoints(unittest.TestCase):
    """Test suite for FastAPI REST API endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.sample_rate = 22050

    def _create_wav_bytes(self, duration_sec: float = 3.5, f0: float = 146.83) -> bytes:
        """Generates valid WAV audio bytes in memory."""
        sr = self.sample_rate
        t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False, dtype=np.float32)
        # Fundamental Sa + Pa fifth
        sig = 0.6 * np.sin(2 * np.pi * f0 * t) + 0.3 * np.sin(2 * np.pi * (f0 * 1.5) * t)

        # Percussive clicks (every 0.5s = 120 bpm)
        beat_interval = int(sr * 0.5)
        for b in range(0, len(sig), beat_interval):
            decay = np.exp(-np.linspace(0, 10, min(1000, len(sig) - b)))
            sig[b : b + len(decay)] += 0.5 * decay

        sig = np.clip(sig / np.max(np.abs(sig)) * 0.85, -1.0, 1.0)
        int_data = (sig * 32767).astype(np.int16)

        buf = io.BytesIO()
        wavfile.write(buf, sr, int_data)
        return buf.getvalue()

    # ========================================================================
    # Health Endpoint Tests
    # ========================================================================

    def test_health_endpoint(self):
        """GET /api/v1/health returns 200 OK with correct schema without heavy processing."""
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["version"], settings.app_version)
        self.assertIn("services", data)
        self.assertEqual(data["services"]["api"], "operational")
        self.assertEqual(data["services"]["dsp_engine"], "available")
        self.assertIn("timestamp", data)

    def test_root_redirects_to_docs(self):
        """GET / redirects to /docs."""
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "/docs")

    # ========================================================================
    # Ragas Catalog Endpoint Tests
    # ========================================================================

    def test_list_ragas_all(self):
        """GET /api/v1/ragas returns complete list of registered ragas."""
        response = self.client.get("/api/v1/ragas")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["total"], 60)
        self.assertEqual(len(data["ragas"]), data["total"])

        # Check fields of first raga
        first_raga = data["ragas"][0]
        self.assertIn("id", first_raga)
        self.assertIn("name", first_raga)
        self.assertIn("thaat", first_raga)
        self.assertIn("aroha", first_raga)
        self.assertIn("avaroha", first_raga)

    def test_list_ragas_filter_by_thaat(self):
        """GET /api/v1/ragas?thaat=Kalyan filters by Thaat."""
        response = self.client.get("/api/v1/ragas?thaat=Kalyan")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 0)
        for raga in data["ragas"]:
            self.assertIn("kalyan", raga["thaat"].lower())

    def test_list_ragas_search(self):
        """GET /api/v1/ragas?search=yaman searches by name."""
        response = self.client.get("/api/v1/ragas?search=yaman")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 0)
        raga_ids = [r["id"] for r in data["ragas"]]
        self.assertIn("yaman", raga_ids)

    def test_get_raga_by_id_success(self):
        """GET /api/v1/ragas/yaman returns Yaman details."""
        response = self.client.get("/api/v1/ragas/yaman")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "yaman")
        self.assertEqual(data["name"], "Yaman")
        self.assertEqual(data["thaat"], "Kalyan")
        self.assertIn("G", data["vadi"])
        self.assertIn("N", data["samvadi"])

    def test_get_raga_by_alias(self):
        """GET /api/v1/ragas/bhairabi resolves alias to bhairavi."""
        response = self.client.get("/api/v1/ragas/bhairabi")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "bhairavi")

    def test_get_raga_by_id_not_found(self):
        """GET /api/v1/ragas/non_existent_raga_xyz returns 404."""
        response = self.client.get("/api/v1/ragas/non_existent_raga_xyz")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["error_code"], "RAGA_NOT_FOUND")

    # ========================================================================
    # Talas Catalog Endpoint Tests
    # ========================================================================

    def test_list_talas_all(self):
        """GET /api/v1/talas returns registered talas."""
        response = self.client.get("/api/v1/talas")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["total"], 6)

        tala_ids = [t["id"] for t in data["talas"]]
        self.assertIn("teental", tala_ids)
        self.assertIn("jhaptaal", tala_ids)
        self.assertIn("ektaal", tala_ids)
        self.assertIn("rupak", tala_ids)

    def test_list_talas_filter_by_matras(self):
        """GET /api/v1/talas?matras=16 returns 16-beat talas."""
        response = self.client.get("/api/v1/talas?matras=16")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 0)
        for tala in data["talas"]:
            self.assertEqual(tala["matras"], 16)

    def test_get_tala_by_id_success(self):
        """GET /api/v1/talas/teental returns Teental structure."""
        response = self.client.get("/api/v1/talas/teental")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "teental")
        self.assertEqual(data["matras"], 16)
        self.assertEqual(data["vibhag"], "4+4+4+4")
        self.assertEqual(data["sam_position"], 1)
        self.assertEqual(data["khali_positions"], [9])

    def test_get_tala_by_id_not_found(self):
        """GET /api/v1/talas/non_existent_tala_xyz returns 404."""
        response = self.client.get("/api/v1/talas/non_existent_tala_xyz")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["error_code"], "TALA_NOT_FOUND")

    # ========================================================================
    # Audio Analysis Endpoint Tests
    # ========================================================================

    def test_analyze_valid_audio_upload(self):
        """POST /api/v1/analyze with valid WAV returns 200 OK and complete AnalysisResponse."""
        wav_bytes = self._create_wav_bytes(duration_sec=3.5, f0=146.83)
        files = {"file": ("test_recording.wav", wav_bytes, "audio/wav")}

        response = self.client.post("/api/v1/analyze", files=files)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], "completed")
        self.assertIn("analysis_id", data)

        # Audio metadata
        meta = data["audio_metadata"]
        self.assertEqual(meta["filename"], "test_recording.wav")
        self.assertAlmostEqual(meta["duration_seconds"], 3.5, places=1)
        self.assertEqual(meta["sample_rate"], 22050)

        # Tonic
        self.assertIsNotNone(data["tonic"]["frequency_hz"])
        self.assertGreater(data["tonic"]["frequency_hz"], 50.0)
        self.assertGreaterEqual(data["tonic"]["confidence"], 0.0)
        self.assertLessEqual(data["tonic"]["confidence"], 1.0)

        # Swara
        self.assertIn("S", data["swara"]["pitch_class_distribution"])

        # Raga
        self.assertIsNotNone(data["raga"]["name"])
        self.assertGreaterEqual(data["raga"]["confidence"], 0.0)

        # Rhythm & Tala
        self.assertIsNotNone(data["rhythm"]["laya"])
        self.assertIsNotNone(data["tala"]["name"])

        # Processing time
        self.assertGreater(data["processing_time_ms"], 0.0)

    def test_analyze_empty_file_rejected(self):
        """POST /api/v1/analyze with 0 bytes returns 422 Unprocessable Entity."""
        files = {"file": ("empty.wav", b"", "audio/wav")}
        response = self.client.post("/api/v1/analyze", files=files)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertEqual(data["error_code"], "EMPTY_FILE")

    def test_analyze_unsupported_format_rejected(self):
        """POST /api/v1/analyze with unsupported extension (.txt/.exe) returns 400."""
        files = {"file": ("script.py", b"print('hello')", "text/plain")}
        response = self.client.post("/api/v1/analyze", files=files)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error_code"], "INVALID_AUDIO_FORMAT")

    def test_analyze_corrupt_header_rejected(self):
        """POST /api/v1/analyze with invalid audio header returns 400."""
        # 100 bytes of arbitrary text saved with .wav extension
        corrupt_bytes = b"CORRUPTED_NON_AUDIO_DATA_" * 10
        files = {"file": ("corrupt.wav", corrupt_bytes, "audio/wav")}
        response = self.client.post("/api/v1/analyze", files=files)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error_code"], "INVALID_AUDIO_FORMAT")

    def test_analyze_path_traversal_filename_sanitized(self):
        """POST /api/v1/analyze with path traversal filename is safely sanitized."""
        wav_bytes = self._create_wav_bytes(duration_sec=3.0, f0=130.81)
        # Attempt malicious filename
        malicious_filename = "../../../etc/passwd.wav"
        files = {"file": (malicious_filename, wav_bytes, "audio/wav")}

        response = self.client.post("/api/v1/analyze", files=files)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Filename in response should have stripped directory traversal
        self.assertNotIn("..", data["audio_metadata"]["filename"])
        self.assertNotIn("/", data["audio_metadata"]["filename"])
        self.assertEqual(data["audio_metadata"]["filename"], "passwd.wav")

    # ========================================================================
    # Planned Contract Placeholder Tests (501 Not Implemented)
    # ========================================================================

    def test_get_analysis_by_id_returns_501_not_implemented(self):
        """GET /api/v1/analysis/{id} returns 501 per Phase 6 contract."""
        response = self.client.get("/api/v1/analysis/sample-job-id-12345")
        self.assertEqual(response.status_code, 501)
        data = response.json()
        self.assertEqual(data["error_code"], "FEATURE_NOT_IMPLEMENTED")
        self.assertIn("endpoint", data["details"])

    def test_post_generate_returns_200_with_symbolic_composition(self):
        """POST /api/v1/generate returns 200 with validated SymbolicComposition."""
        payload = {
            "raga_id": "yaman",
            "tala_id": "teental",
            "style_id": "bandish",
            "tempo_bpm": 84,
            "duration_seconds": 60,
            "creativity_score": 50,
            "seed": 12345,
        }
        response = self.client.post("/api/v1/generate", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("composition_id", data)
        self.assertIn("symbolic_composition", data)
        self.assertEqual(data["symbolic_composition"]["raga_name"], "Yaman")
        self.assertEqual(data["symbolic_composition"]["tala_name"], "Teental")
        self.assertGreater(len(data["symbolic_composition"]["events"]), 0)
        self.assertTrue(data["validation_result"]["valid"])

    def test_post_explain_returns_structured_explanation(self):
        """POST /api/v1/explain returns structured musicological commentary."""
        payload = {
            "raga_name": "Bhairav",
            "thaat": "Bhairav",
            "vadi": "d",
            "samvadi": "r",
            "aroha": ["S", "r", "G", "m", "P", "d", "N", "S'"],
            "avaroha": ["S'", "N", "d", "P", "m", "G", "r", "S"],
            "tonic_note": "C#",
            "tonic_hz": 138.59,
            "tala_name": "Teental",
            "matras": 16,
            "bpm": 80.0,
            "laya": "Madhya",
        }
        response = self.client.post("/api/v1/explain", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("summary", data)
        self.assertIn("raga_explanation", data)
        self.assertIn("tala_explanation", data)
        self.assertIn("educational_notes", data)
        self.assertIsInstance(data["educational_notes"], list)

    # ========================================================================
    # Saraga Hindustani Smoke Test
    # ========================================================================

    def test_saraga_integration_smoke_test(self):
        """
        Integration smoke test verifying analysis behavior on a real Hindustani recording excerpt
        or dataset adapter track.
        """
        from backend.app.utils.dataset_adapter import SaragaDatasetAdapter
        
        adapter = SaragaDatasetAdapter()
        track_dirs = adapter.scan_dataset()
        self.assertGreater(len(track_dirs), 0)

        # Retrieve annotations for the first discovered track
        track_meta = adapter.get_track_annotations(track_dirs[0])
        tonic_hz = track_meta.tonic_hz or 146.83
        raga_title = track_meta.raga_names[0] if track_meta.raga_names else "smoke_test_raga"
        
        wav_bytes = self._create_wav_bytes(duration_sec=3.5, f0=tonic_hz)
        files = {"file": (f"{raga_title}_smoke.wav", wav_bytes, "audio/wav")}

        response = self.client.post("/api/v1/analyze", files=files)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], "completed")
        self.assertIsNotNone(data["tonic"]["frequency_hz"])
        self.assertIsNotNone(data["raga"]["name"])
        self.assertIsNotNone(data["tala"]["name"])
        self.assertGreater(data["processing_time_ms"], 0.0)


if __name__ == "__main__":
    unittest.main()
