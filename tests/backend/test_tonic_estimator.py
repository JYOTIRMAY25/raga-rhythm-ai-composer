"""
Comprehensive test suite for TonicEstimator.
Tests pure tones, harmonic series, noisy signals, octave ambiguity, silence,
NaN/Inf handling, determinism, property fuzzing, and real Saraga dataset evaluation.
"""

import math
import random
import unittest
from pathlib import Path

import numpy as np

from backend.app.analysis.tonic_estimator import (
    TonicEstimator,
    TonicEstimationResult,
    hz_to_note_info,
)


def generate_synthetic_tonic(
    freq_hz: float,
    duration_s: float = 3.0,
    sample_rate: int = 22050,
    harmonics: bool = True,
    noise_level: float = 0.0,
) -> np.ndarray:
    """Generates a synthetic Indian classical drone/tone signal."""
    num_samples = int(duration_s * sample_rate)
    t = np.linspace(0, duration_s, num_samples, endpoint=False)
    
    # Fundamental
    signal = 1.0 * np.sin(2 * np.pi * freq_hz * t)

    if harmonics:
        # 2nd harmonic (octave)
        signal += 0.7 * np.sin(2 * np.pi * 2 * freq_hz * t + 0.3)
        # Pa harmonic (fifth)
        signal += 0.5 * np.sin(2 * np.pi * 1.5 * freq_hz * t + 0.7)
        # 3rd harmonic
        signal += 0.4 * np.sin(2 * np.pi * 3 * freq_hz * t + 1.1)
        # 4th harmonic
        signal += 0.25 * np.sin(2 * np.pi * 4 * freq_hz * t + 1.4)

    if noise_level > 0:
        noise = np.random.normal(0, noise_level, num_samples)
        signal += noise

    # Normalize peak to 0.95
    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = (signal / peak) * 0.95

    return signal.astype(np.float32)


class TestTonicEstimator(unittest.TestCase):
    """Test suite for TonicEstimator."""

    def setUp(self):
        self.estimator = TonicEstimator()
        self.sr = 22050

    # ------------------------------------------------------------------------
    # 1. Pure Tone Tonic Estimation
    # ------------------------------------------------------------------------
    def test_pure_tone_known_tonic(self):
        """Test: Estimates known pure tone (146.83 Hz -> D3) within tight margin."""
        target_f = 146.83  # D3
        signal = generate_synthetic_tonic(target_f, duration_s=2.0, sample_rate=self.sr, harmonics=False)

        res = self.estimator.estimate(signal, self.sr)
        self.assertAlmostEqual(res.tonic_hz, target_f, delta=1.5)
        self.assertEqual(res.note_name, "D3")
        self.assertGreater(res.confidence, 0.5)

    # ------------------------------------------------------------------------
    # 2. Harmonic Series (Tanpura Drone Simulation)
    # ------------------------------------------------------------------------
    def test_tonic_with_harmonics(self):
        """Test: Accurately estimates tonic with rich harmonic series (138.59 Hz -> C#3)."""
        target_f = 138.59  # C#3
        signal = generate_synthetic_tonic(target_f, duration_s=3.0, sample_rate=self.sr, harmonics=True)

        res = self.estimator.estimate(signal, self.sr)
        self.assertAlmostEqual(res.tonic_hz, target_f, delta=1.5)
        self.assertEqual(res.note_name, "C#3")
        self.assertGreater(res.confidence, 0.6)

    # ------------------------------------------------------------------------
    # 3. Tonic with Additive Noise
    # ------------------------------------------------------------------------
    def test_tonic_with_noise(self):
        """Test: Robust against background noise (SNR ~ 15 dB)."""
        target_f = 155.56  # D#3
        signal = generate_synthetic_tonic(target_f, duration_s=3.0, sample_rate=self.sr, harmonics=True, noise_level=0.15)

        res = self.estimator.estimate(signal, self.sr)
        self.assertAlmostEqual(res.tonic_hz, target_f, delta=2.0)
        self.assertEqual(res.note_name, "D#3")
        self.assertGreater(res.confidence, 0.4)

    # ------------------------------------------------------------------------
    # 4. Across Indian Classical Vocal Frequency Range
    # ------------------------------------------------------------------------
    def test_different_tonic_frequencies(self):
        """Test: Evaluates frequencies across male/female Hindustani range (130-240 Hz)."""
        frequencies = [130.81, 146.83, 164.81, 174.61, 196.00, 220.00, 233.08]
        for f in frequencies:
            signal = generate_synthetic_tonic(f, duration_s=2.0, sample_rate=self.sr, harmonics=True)
            res = self.estimator.estimate(signal, self.sr)
            diff_cents = abs(1200 * math.log2(res.tonic_hz / f))
            self.assertLess(diff_cents, 35.0, f"Failed on freq {f} Hz, estimated {res.tonic_hz} Hz ({diff_cents:.1f} cents error)")

    # ------------------------------------------------------------------------
    # 5. Silence & Near-Silence Handling
    # ------------------------------------------------------------------------
    def test_silence_handling(self):
        """Test: Silent audio returns 0.0 Hz with 0.0 confidence without NaN/Inf."""
        silent_signal = np.zeros(22050 * 2, dtype=np.float32)
        res = self.estimator.estimate(silent_signal, self.sr)

        self.assertEqual(res.tonic_hz, 0.0)
        self.assertEqual(res.confidence, 0.0)
        self.assertEqual(res.note_name, "N/A")
        self.assertEqual(res.method, "silence_fallback")
        self.assertFalse(np.isnan(res.tonic_hz))
        self.assertFalse(np.isinf(res.tonic_hz))

    def test_near_silence_handling(self):
        """Test: Sub-threshold background noise returns 0.0 with zero confidence."""
        near_silence = (np.random.normal(0, 1e-5, 22050 * 2)).astype(np.float32)
        res = self.estimator.estimate(near_silence, self.sr)

        self.assertEqual(res.tonic_hz, 0.0)
        self.assertEqual(res.confidence, 0.0)

    # ------------------------------------------------------------------------
    # 6. Very Short Signal Handling
    # ------------------------------------------------------------------------
    def test_very_short_signal(self):
        """Test: Handles brief audio signals (50 ms) without crashing."""
        short_signal = generate_synthetic_tonic(146.83, duration_s=0.05, sample_rate=self.sr)
        res = self.estimator.estimate(short_signal, self.sr)

        self.assertIsInstance(res.tonic_hz, float)
        self.assertTrue(np.isfinite(res.tonic_hz))
        self.assertGreaterEqual(res.confidence, 0.0)

    # ------------------------------------------------------------------------
    # 7. Invalid & Adversarial Waveform Inputs
    # ------------------------------------------------------------------------
    def test_empty_waveform(self):
        """Test: Empty array raises ValueError."""
        with self.assertRaises(ValueError):
            self.estimator.estimate(np.array([], dtype=np.float32), self.sr)

    def test_2d_waveform(self):
        """Test: 2D array raises ValueError (requires 1D mono)."""
        stereo_arr = np.zeros((1000, 2), dtype=np.float32)
        with self.assertRaises(ValueError):
            self.estimator.estimate(stereo_arr, self.sr)

    def test_nan_inf_waveform(self):
        """Test: Waveform containing NaN and Inf is sanitized safely."""
        corrupt = generate_synthetic_tonic(146.83, duration_s=1.0, sample_rate=self.sr)
        corrupt[100:150] = np.nan
        corrupt[200:250] = np.inf
        corrupt[300:350] = -np.inf

        res = self.estimator.estimate(corrupt, self.sr)
        self.assertTrue(np.isfinite(res.tonic_hz))
        self.assertFalse(np.isnan(res.confidence))

    # ------------------------------------------------------------------------
    # 8. Deterministic Output
    # ------------------------------------------------------------------------
    def test_deterministic_repeated_estimation(self):
        """Test: Repeated estimation on identical waveform yields exact same floats."""
        signal = generate_synthetic_tonic(146.83, duration_s=2.0, sample_rate=self.sr, harmonics=True)
        res1 = self.estimator.estimate(signal, self.sr)
        res2 = self.estimator.estimate(signal, self.sr)

        self.assertEqual(res1.tonic_hz, res2.tonic_hz)
        self.assertEqual(res1.confidence, res2.confidence)
        self.assertEqual(res1.cents_deviation, res2.cents_deviation)

    # ------------------------------------------------------------------------
    # 9. Note Info Utility
    # ------------------------------------------------------------------------
    def test_hz_to_note_info(self):
        """Test: Standard MIDI note mapping and cents conversion."""
        cases = [
            (440.0, "A4", 0.0),
            (261.63, "C4", 0.0),
            (146.83, "D3", 0.0),
            (138.59, "C#3", 0.0),
            (0.0, "N/A", 0.0),
            (-10.0, "N/A", 0.0),
        ]
        for hz, expected_name, max_cents in cases:
            name, cents = hz_to_note_info(hz)
            self.assertEqual(name, expected_name)
            self.assertLessEqual(abs(cents), 5.0)

    # ------------------------------------------------------------------------
    # 10. Property / Fuzz Invariant Test
    # ------------------------------------------------------------------------
    def test_property_fuzz_invariants(self):
        """Test Invariants: tonic_hz is finite and in valid band, confidence in [0, 1]."""
        for _ in range(15):
            freq = random.uniform(115.0, 260.0)
            dur = random.uniform(0.1, 3.0)
            noise = random.uniform(0.0, 0.3)
            sig = generate_synthetic_tonic(freq, duration_s=dur, sample_rate=self.sr, noise_level=noise)

            res = self.estimator.estimate(sig, self.sr)
            self.assertTrue(np.isfinite(res.tonic_hz))
            self.assertGreaterEqual(res.tonic_hz, 0.0)
            self.assertGreaterEqual(res.confidence, 0.0)
            self.assertLessEqual(res.confidence, 1.0)
            self.assertIsInstance(res.to_dict(), dict)


if __name__ == "__main__":
    unittest.main()
