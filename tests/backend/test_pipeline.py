"""
Comprehensive unit and integration test suite for AnalysisPipeline.
"""

from __future__ import annotations

import math
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from backend.app.analysis.pipeline import (
    AnalysisPipeline,
    UnifiedAnalysisResult,
    PipelineAudioMetadata,
    PipelineTonicResult,
    PipelinePitchSummary,
    PipelineSwaraSummary,
    PipelineRagaResult,
    PipelineRhythmSummary,
    PipelineBeatGridSummary,
    PipelineTalaResult,
    _sanitize_float,
    _clamp_confidence,
)
from backend.app.analysis.preprocessor import (
    AudioPreprocessingError,
    AudioTooLongError,
    InvalidAudioError,
)


class TestAnalysisPipeline(unittest.TestCase):
    """Test suite for unified AnalysisPipeline orchestration."""

    def setUp(self):
        self.pipeline = AnalysisPipeline()
        self.sample_rate = 22050
        self.temp_dir = Path(tempfile.gettempdir()) / "test_ragarhythm_pipeline"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        # Clean up temporary test files
        if self.temp_dir.exists():
            for f in self.temp_dir.glob("*"):
                try:
                    f.unlink()
                except Exception:
                    pass

    def _create_synthetic_audio(
        self,
        duration_sec: float = 4.0,
        f0: float = 140.0,
        with_beats: bool = True,
    ) -> np.ndarray:
        """Creates a clean synthetic Hindustani audio signal (tonic + harmonics + percussive clicks)."""
        sr = self.sample_rate
        t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False, dtype=np.float32)
        
        # Harmonic drone / melody
        sig = 0.5 * np.sin(2 * np.pi * f0 * t)
        sig += 0.3 * np.sin(2 * np.pi * 2 * f0 * t)
        sig += 0.2 * np.sin(2 * np.pi * 3 * f0 * t)

        # Add periodic percussive transients (e.g. 120 BPM = 0.5s intervals)
        if with_beats:
            beat_interval = int(sr * 0.5)
            for b in range(0, len(sig), beat_interval):
                decay = np.exp(-np.linspace(0, 10, min(1000, len(sig) - b)))
                sig[b : b + len(decay)] += 0.8 * decay

        # Normalize
        max_val = np.max(np.abs(sig))
        if max_val > 0:
            sig = sig / max_val * 0.85
        return sig.astype(np.float32)

    def _save_temp_wav(self, waveform: np.ndarray, filename: str = "test_synth.wav") -> Path:
        """Helper to save a waveform to temporary WAV file."""
        file_path = self.temp_dir / filename
        # Convert float32 [-1.0, 1.0] to int16 for standard wav
        int_data = (np.clip(waveform, -1.0, 1.0) * 32767).astype(np.int16)
        wavfile.write(str(file_path), self.sample_rate, int_data)
        return file_path

    def test_pipeline_orchestration_waveform(self):
        """Tests that process_waveform executes all stages and produces valid UnifiedAnalysisResult."""
        waveform = self._create_synthetic_audio(duration_sec=3.5, f0=146.83)
        result = self.pipeline.process_waveform(waveform, sample_rate=self.sample_rate)

        self.assertIsInstance(result, UnifiedAnalysisResult)
        self.assertGreater(result.audio_metadata.duration_seconds, 3.0)
        self.assertEqual(result.audio_metadata.sample_rate, 22050)
        self.assertFalse(result.audio_metadata.is_silent)

        # Stage timings and total processing time
        self.assertGreater(result.processing_time_ms, 0.0)
        self.assertIn("preprocessing", result.stage_timings_ms)
        self.assertIn("tonic_estimation", result.stage_timings_ms)
        self.assertIn("pitch_extraction", result.stage_timings_ms)
        self.assertIn("tonic_resolution", result.stage_timings_ms)
        self.assertIn("swara_analysis", result.stage_timings_ms)
        self.assertIn("raga_detection", result.stage_timings_ms)
        self.assertIn("rhythm_analysis", result.stage_timings_ms)
        self.assertIn("tala_classification", result.stage_timings_ms)
        self.assertIn("beat_tracking", result.stage_timings_ms)

        # Tonic
        self.assertIsNotNone(result.tonic.frequency_hz)
        self.assertGreater(result.tonic.frequency_hz, 50.0)
        self.assertGreaterEqual(result.tonic.confidence, 0.0)
        self.assertLessEqual(result.tonic.confidence, 1.0)

        # Pitch
        self.assertGreater(result.pitch.total_frames, 0)
        self.assertGreaterEqual(result.pitch.voiced_percentage, 0.0)
        self.assertLessEqual(result.pitch.voiced_percentage, 100.0)

        # Swara
        self.assertIsInstance(result.swara.pitch_class_distribution, dict)
        self.assertIn("S", result.swara.pitch_class_distribution)

        # Raga
        self.assertIsNotNone(result.raga.predicted_raga)
        self.assertGreaterEqual(result.raga.confidence, 0.0)
        self.assertLessEqual(result.raga.confidence, 1.0)

        # Rhythm & Tala
        self.assertGreater(result.rhythm.total_onsets, 0)
        self.assertGreaterEqual(result.rhythm.tempo_confidence, 0.0)
        self.assertIsNotNone(result.tala.predicted_tala)
        self.assertGreaterEqual(result.tala.confidence, 0.0)
        self.assertLessEqual(result.tala.confidence, 1.0)

    def test_pipeline_process_file(self):
        """Tests that process_file works correctly from disk file."""
        waveform = self._create_synthetic_audio(duration_sec=3.0, f0=130.81)
        temp_file = self._save_temp_wav(waveform, "test_file_run.wav")

        result = self.pipeline.process_file(temp_file)
        self.assertIsInstance(result, UnifiedAnalysisResult)
        self.assertEqual(result.audio_metadata.filename, "test_file_run.wav")
        self.assertIsNotNone(result.audio_metadata.file_path)
        self.assertAlmostEqual(result.audio_metadata.duration_seconds, 3.0, places=1)

    def test_pipeline_handles_silent_audio(self):
        """Tests that silence produces graceful fallback results with appropriate warnings."""
        silence = np.zeros(int(self.sample_rate * 2.0), dtype=np.float32)
        result = self.pipeline.process_waveform(silence, sample_rate=self.sample_rate)

        self.assertTrue(result.audio_metadata.is_silent)
        warning_codes = [w.code for w in result.warnings]
        self.assertIn("AUDIO_SILENT", warning_codes)
        self.assertIn("AUDIO_SHORT", warning_codes)

        # Confidences should be 0.0
        self.assertEqual(result.rhythm.tempo_confidence, 0.0)
        self.assertEqual(result.tala.confidence, 0.0)

    def test_pipeline_handles_short_audio_warning(self):
        """Tests that audio under 3.0s emits AUDIO_SHORT warning."""
        short_audio = self._create_synthetic_audio(duration_sec=1.5, f0=140.0)
        result = self.pipeline.process_waveform(short_audio, sample_rate=self.sample_rate)

        warning_codes = [w.code for w in result.warnings]
        self.assertIn("AUDIO_SHORT", warning_codes)

    def test_nan_and_infinity_sanitization(self):
        """Tests helper sanitizers for float NaN / Inf values."""
        self.assertIsNone(_sanitize_float(float("nan")))
        self.assertIsNone(_sanitize_float(float("inf")))
        self.assertIsNone(_sanitize_float(float("-inf")))
        self.assertEqual(_sanitize_float(142.5), 142.5)
        self.assertEqual(_sanitize_float(float("nan"), default=0.0), 0.0)

        # Clamping confidence
        self.assertEqual(_clamp_confidence(1.5), 1.0)
        self.assertEqual(_clamp_confidence(-0.5), 0.0)
        self.assertEqual(_clamp_confidence(float("nan")), 0.0)
        self.assertEqual(_clamp_confidence(0.75), 0.75)

    def test_non_existent_file_raises_error(self):
        """Tests that non-existent file paths properly raise FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            self.pipeline.process_file("non_existent_audio_path_xyz.wav")

    def test_empty_file_raises_invalid_audio_error(self):
        """Tests that 0-byte audio file properly raises InvalidAudioError."""
        empty_file = self.temp_dir / "empty_test.wav"
        empty_file.write_bytes(b"")
        with self.assertRaises(InvalidAudioError):
            self.pipeline.process_file(empty_file)


if __name__ == "__main__":
    unittest.main()
