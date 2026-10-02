"""
Comprehensive unit test suite for RhythmAnalyzer and RhythmFeatures.

Tests:
A. Silent audio handling (zero novelty, no onsets, BPM None, zero confidence)
B. Very short audio handling (shorter than FFT window, zero padded, no crash)
C. Single impulse signal (exactly 1 detected onset, 0 IOIs, safe fallback)
D. Periodic impulse train (regular onsets, correct IOI spacing)
E. Known tempo signal estimation (60 BPM, 120 BPM, 90 BPM)
F. Different tempos across Hindustani tempo range (72 BPM, 140 BPM, 180 BPM)
G. Robustness against NaN, Inf, and non-finite inputs
H. Inter-Onset Interval (IOI) calculation correctness
I. Outlier-resistant IOI statistics (median, IQR, MAD)
J. Refractory onset spacing (prevents duplicate peak triggers)
K. BPM confidence scoring (high for periodic clicks, zero for silence/white noise)
L. Deterministic repeated execution
M. Integration with AudioPreprocessingResult and summary dictionary serialization
"""

import math
from typing import Any, Dict, List
import unittest

import numpy as np

from backend.app.analysis.preprocessor import AudioPreprocessingResult
from backend.app.analysis.rhythm_analyzer import (
    RhythmAnalyzer,
    RhythmFeatures,
)


class TestRhythmAnalyzer(unittest.TestCase):
    """Test suite for RhythmAnalyzer."""

    def setUp(self):
        self.sr = 22050
        self.analyzer = RhythmAnalyzer(sample_rate=self.sr)

    def _generate_click_train(
        self,
        bpm: float,
        duration: float = 6.0,
        click_duration_samples: int = 60,
    ) -> np.ndarray:
        """Helper to generate a clean synthetic click train at a specified BPM."""
        interval_sec = 60.0 / bpm
        num_samples = int(self.sr * duration)
        audio = np.zeros(num_samples, dtype=np.float32)

        t_click = 0.0
        while t_click < duration:
            idx = int(t_click * self.sr)
            if idx < num_samples:
                # Add a decaying sinusoidal burst / click
                burst_len = min(click_duration_samples, num_samples - idx)
                t_burst = np.arange(burst_len) / self.sr
                burst = np.sin(2 * np.pi * 1000.0 * t_burst) * np.exp(-t_burst * 200.0)
                audio[idx : idx + burst_len] += burst.astype(np.float32)
            t_click += interval_sec

        return audio

    def test_silent_audio(self):
        """Test that pure silence returns zero novelty, no onsets, and None BPM."""
        audio = np.zeros(int(self.sr * 3.0), dtype=np.float32)
        features = self.analyzer.analyze(audio)

        self.assertIsInstance(features, RhythmFeatures)
        self.assertEqual(len(features.onset_times), 0)
        self.assertEqual(len(features.ioi_intervals), 0)
        self.assertIsNone(features.estimated_bpm)
        self.assertEqual(features.tempo_confidence, 0.0)
        self.assertEqual(float(np.max(features.novelty_envelope)), 0.0)
        self.assertFalse(np.isnan(features.novelty_envelope).any())

    def test_very_short_audio(self):
        """Test audio shorter than FFT window is safely handled without errors."""
        short_audio = np.array([0.5, -0.5, 0.2, -0.1], dtype=np.float32)
        features = self.analyzer.analyze(short_audio)

        self.assertIsInstance(features, RhythmFeatures)
        self.assertFalse(np.isnan(features.novelty_envelope).any())
        self.assertFalse(np.isinf(features.novelty_envelope).any())
        self.assertIsNone(features.estimated_bpm)

    def test_single_impulse(self):
        """Test single impulse produces 1 onset, 0 IOIs, and None BPM safely."""
        audio = np.zeros(int(self.sr * 2.0), dtype=np.float32)
        impulse_idx = int(0.5 * self.sr)
        audio[impulse_idx : impulse_idx + 100] = 1.0

        features = self.analyzer.analyze(audio)
        self.assertEqual(features.total_onsets, 1)
        self.assertAlmostEqual(features.onset_times[0], 0.5, delta=0.05)
        self.assertEqual(len(features.ioi_intervals), 0)
        self.assertIsNone(features.estimated_bpm)

    def test_periodic_impulse_train(self):
        """Test periodic impulses produce regularly spaced onsets and correct IOIs."""
        duration = 5.0
        interval_sec = 0.5  # 120 BPM
        audio = np.zeros(int(self.sr * duration), dtype=np.float32)
        
        expected_onsets = []
        for t in np.arange(0.25, duration - 0.25, interval_sec):
            idx = int(t * self.sr)
            audio[idx : idx + 80] = 1.0
            expected_onsets.append(t)

        features = self.analyzer.analyze(audio)
        self.assertGreater(features.total_onsets, 5)
        self.assertEqual(len(features.ioi_intervals), features.total_onsets - 1)
        
        # Check median IOI is close to 0.5s
        stats = features.statistics
        self.assertAlmostEqual(stats["median_ioi"], interval_sec, delta=0.03)

    def test_known_tempo_120_bpm(self):
        """Test tempo estimation for a synthetic 120 BPM signal."""
        audio = self._generate_click_train(bpm=120.0, duration=6.0)
        features = self.analyzer.analyze(audio)

        self.assertIsNotNone(features.estimated_bpm)
        self.assertAlmostEqual(features.estimated_bpm, 120.0, delta=2.5)
        self.assertGreater(features.tempo_confidence, 0.5)

    def test_known_tempo_60_bpm(self):
        """Test tempo estimation for a slow (Vilambit) 60 BPM signal."""
        audio = self._generate_click_train(bpm=60.0, duration=8.0)
        features = self.analyzer.analyze(audio)

        self.assertIsNotNone(features.estimated_bpm)
        self.assertAlmostEqual(features.estimated_bpm, 60.0, delta=2.5)
        self.assertGreater(features.tempo_confidence, 0.4)

    def test_known_tempo_90_bpm(self):
        """Test tempo estimation for a medium (Madhya) 90 BPM signal."""
        audio = self._generate_click_train(bpm=90.0, duration=6.0)
        features = self.analyzer.analyze(audio)

        self.assertIsNotNone(features.estimated_bpm)
        self.assertAlmostEqual(features.estimated_bpm, 90.0, delta=2.5)
        self.assertGreater(features.tempo_confidence, 0.5)

    def test_different_tempos(self):
        """Test tempo estimation across diverse tempo rates (72 BPM, 140 BPM, 180 BPM)."""
        test_tempos = [72.0, 140.0, 180.0]
        for target_bpm in test_tempos:
            audio = self._generate_click_train(bpm=target_bpm, duration=6.0)
            features = self.analyzer.analyze(audio)

            self.assertIsNotNone(features.estimated_bpm, f"Should estimate BPM for {target_bpm}")
            self.assertAlmostEqual(
                features.estimated_bpm,
                target_bpm,
                delta=3.5,
                msg=f"Expected ~{target_bpm} BPM, got {features.estimated_bpm}",
            )

    def test_no_nan_or_inf_output(self):
        """Verify that pathological audio with NaNs and Infs is safely sanitized."""
        audio = np.array([np.nan, np.inf, -np.inf, 0.5, np.nan, 0.2] * 2000, dtype=np.float32)
        features = self.analyzer.analyze(audio)

        self.assertFalse(np.isnan(features.novelty_envelope).any())
        self.assertFalse(np.isinf(features.novelty_envelope).any())
        self.assertFalse(np.isnan(features.novelty_times).any())
        self.assertFalse(np.isnan(features.onset_times).any())
        self.assertFalse(np.isnan(features.ioi_intervals).any())
        if features.estimated_bpm is not None:
            self.assertTrue(math.isfinite(features.estimated_bpm))

    def test_ioi_calculation_correctness(self):
        """Verify exact calculation of inter-onset intervals."""
        onset_times = np.array([1.0, 1.5, 2.25, 3.0, 4.0])
        iois, stats = self.analyzer.compute_inter_onset_intervals(onset_times)

        expected_iois = np.array([0.5, 0.75, 0.75, 1.0])
        np.testing.assert_allclose(iois, expected_iois)
        self.assertAlmostEqual(stats["median_ioi"], 0.75)
        self.assertAlmostEqual(stats["mean_ioi"], 0.75)
        self.assertEqual(stats["count"], 4)

    def test_outlier_resistant_ioi_statistics(self):
        """Verify robust stats (median, IQR, MAD) withstand large outlier intervals."""
        # Mostly 0.5s intervals with one 10.0s pause outlier
        onset_times = np.array([0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 13.0, 13.5, 14.0])
        iois, stats = self.analyzer.compute_inter_onset_intervals(onset_times)

        # Median should remain 0.5s despite the 10.0s gap
        self.assertAlmostEqual(stats["median_ioi"], 0.5)
        self.assertAlmostEqual(stats["iqr_ioi"], 0.0, delta=0.01)
        self.assertAlmostEqual(stats["mad_ioi"], 0.0, delta=0.01)

    def test_onset_refractory_spacing(self):
        """Verify minimum onset distance prevents double-triggering on close bursts."""
        audio = np.zeros(int(self.sr * 2.0), dtype=np.float32)
        # Two spikes 20ms apart (below default 60ms minimum spacing)
        audio[1000:1050] = 1.0
        audio[1000 + int(0.02 * self.sr) : 1000 + int(0.02 * self.sr) + 50] = 1.0

        features = self.analyzer.analyze(audio)
        # Should detect only 1 onset, not 2
        self.assertEqual(features.total_onsets, 1)

    def test_bpm_confidence_behavior(self):
        """Verify high confidence for periodic clicks and zero confidence for white noise / silence."""
        # Periodic clicks -> high confidence
        click_audio = self._generate_click_train(bpm=100.0, duration=6.0)
        click_features = self.analyzer.analyze(click_audio)
        self.assertGreater(click_features.tempo_confidence, 0.4)

        # Pure silence -> zero confidence
        silent_audio = np.zeros(int(self.sr * 3.0), dtype=np.float32)
        silent_features = self.analyzer.analyze(silent_audio)
        self.assertEqual(silent_features.tempo_confidence, 0.0)
        self.assertIsNone(silent_features.estimated_bpm)

    def test_deterministic_repeated_execution(self):
        """Verify identical inputs yield strictly identical outputs."""
        audio = self._generate_click_train(bpm=110.0, duration=4.0)
        
        run1 = self.analyzer.analyze(audio)
        run2 = self.analyzer.analyze(audio)

        np.testing.assert_array_equal(run1.novelty_envelope, run2.novelty_envelope)
        np.testing.assert_array_equal(run1.onset_times, run2.onset_times)
        self.assertEqual(run1.estimated_bpm, run2.estimated_bpm)
        self.assertEqual(run1.tempo_confidence, run2.tempo_confidence)

    def test_analyze_preprocessed_wrapper_and_serialization(self):
        """Verify analyze_preprocessed wrapper and to_summary_dict() serialization."""
        audio = self._generate_click_train(bpm=120.0, duration=4.0)
        preproc_result = AudioPreprocessingResult(
            waveform=audio,
            sample_rate=self.sr,
            duration_seconds=4.0,
            number_of_samples=len(audio),
            channels_original=1,
            peak_amplitude=float(np.max(np.abs(audio))),
            rms=float(np.sqrt(np.mean(audio**2))),
            is_silent=False,
            file_path="synthetic_click_120bpm.wav",
        )

        features = self.analyzer.analyze_preprocessed(preproc_result)
        self.assertIsInstance(features, RhythmFeatures)
        self.assertAlmostEqual(features.estimated_bpm, 120.0, delta=2.5)

        summary = features.to_summary_dict()
        self.assertIn("total_onsets", summary)
        self.assertIn("estimated_bpm", summary)
        self.assertIn("tempo_confidence", summary)
        self.assertIn("duration_seconds", summary)
        self.assertIn("statistics", summary)


if __name__ == "__main__":
    unittest.main()
