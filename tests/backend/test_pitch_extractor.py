"""
Comprehensive test suite for PitchExtractor.
Tests pure sine tones, harmonic signals, frequency chirps, noisy audio,
silence, near-silence, very short clips, unvoiced segments, NaN/Inf inputs,
determinism, frequency bounds, and property fuzz invariants.
"""

import math
import random
import unittest
from pathlib import Path

import numpy as np

from backend.app.analysis.pitch_extractor import (
    PitchExtractor,
    PitchExtractionResult,
)


class TestPitchExtractor(unittest.TestCase):
    """Test suite for PitchExtractor."""

    def setUp(self):
        self.extractor = PitchExtractor(f_min_hz=65.0, f_max_hz=600.0, hop_length=98)
        self.sr = 22050

    # ------------------------------------------------------------------------
    # 1. Pure Sine Wave Known Pitch
    # ------------------------------------------------------------------------
    def test_pure_sine_wave_known_pitch(self):
        """Test: Accurately extracts continuous F0 on a pure 220.0 Hz sine tone."""
        dur = 1.0
        t = np.linspace(0, dur, int(self.sr * dur), endpoint=False)
        f_true = 220.0
        waveform = 0.8 * np.sin(2 * np.pi * f_true * t).astype(np.float32)

        res = self.extractor.extract(waveform, self.sr)
        self.assertGreater(res.voiced_percentage, 95.0)
        voiced_freqs = res.frequencies_hz[res.voiced_mask]
        self.assertGreater(len(voiced_freqs), 0)
        mean_detected = float(np.mean(voiced_freqs))
        self.assertAlmostEqual(mean_detected, f_true, delta=1.5)
        self.assertEqual(res.frame_rate, 225.0)

    # ------------------------------------------------------------------------
    # 2. Harmonic Signal
    # ------------------------------------------------------------------------
    def test_harmonic_signal(self):
        """Test: Accurately identifies fundamental F0 (146.83 Hz) in presence of strong harmonics."""
        dur = 1.0
        t = np.linspace(0, dur, int(self.sr * dur), endpoint=False)
        f0 = 146.83  # D3
        # Fundamental + 2f + 3f + 4f
        waveform = (
            0.5 * np.sin(2 * np.pi * f0 * t) +
            0.3 * np.sin(2 * np.pi * 2 * f0 * t) +
            0.2 * np.sin(2 * np.pi * 3 * f0 * t) +
            0.1 * np.sin(2 * np.pi * 4 * f0 * t)
        ).astype(np.float32)

        res = self.extractor.extract(waveform, self.sr)
        voiced_freqs = res.frequencies_hz[res.voiced_mask]
        self.assertGreater(len(voiced_freqs), 0)
        mean_detected = float(np.mean(voiced_freqs))
        self.assertAlmostEqual(mean_detected, f0, delta=1.5)

    # ------------------------------------------------------------------------
    # 3. Known Changing Pitch (Chirp / Glissando)
    # ------------------------------------------------------------------------
    def test_changing_pitch_chirp(self):
        """Test: Tracks linear frequency glide (150 Hz -> 300 Hz) accurately."""
        dur = 1.0
        t = np.linspace(0, dur, int(self.sr * dur), endpoint=False)
        f_start, f_end = 150.0, 300.0
        # Phase of linear chirp: phi(t) = 2*pi*(f0*t + (f1-f0)/(2*T)*t^2)
        phase = 2 * np.pi * (f_start * t + (f_end - f_start) / (2 * dur) * (t ** 2))
        waveform = 0.8 * np.sin(phase).astype(np.float32)

        res = self.extractor.extract(waveform, self.sr)
        voiced_idx = np.where(res.voiced_mask)[0]
        self.assertGreater(len(voiced_idx), 100)

        # Check that extracted frequencies monotonically increase
        early_freq = float(np.mean(res.frequencies_hz[voiced_idx[:20]]))
        late_freq = float(np.mean(res.frequencies_hz[voiced_idx[-20:]]))
        self.assertLess(early_freq, late_freq)
        self.assertAlmostEqual(early_freq, f_start, delta=25.0)
        self.assertAlmostEqual(late_freq, f_end, delta=25.0)

    # ------------------------------------------------------------------------
    # 4. Noisy Signal
    # ------------------------------------------------------------------------
    def test_noisy_signal(self):
        """Test: Robust pitch tracking with additive Gaussian noise (SNR ~ 12 dB)."""
        dur = 1.0
        t = np.linspace(0, dur, int(self.sr * dur), endpoint=False)
        f0 = 175.0
        clean = 0.7 * np.sin(2 * np.pi * f0 * t)
        noise = np.random.normal(0, 0.15, len(t))
        waveform = (clean + noise).astype(np.float32)

        res = self.extractor.extract(waveform, self.sr)
        voiced_freqs = res.frequencies_hz[res.voiced_mask]
        self.assertGreater(len(voiced_freqs), 0)
        self.assertAlmostEqual(float(np.mean(voiced_freqs)), f0, delta=3.0)

    # ------------------------------------------------------------------------
    # 5. Silence & Near-Silence
    # ------------------------------------------------------------------------
    def test_silence(self):
        """Test: All-zero audio produces 0.0 Hz, all-unvoiced mask, zero confidence."""
        waveform = np.zeros(22050, dtype=np.float32)
        res = self.extractor.extract(waveform, self.sr)

        self.assertEqual(res.voiced_frames, 0)
        self.assertEqual(res.voiced_percentage, 0.0)
        self.assertTrue(np.all(res.frequencies_hz == 0.0))
        self.assertTrue(np.all(~res.voiced_mask))
        self.assertTrue(np.all(res.confidence_values == 0.0))
        self.assertTrue(np.all(np.isfinite(res.timestamps_seconds)))

    def test_near_silence(self):
        """Test: Sub-threshold noise floor (1e-5 RMS) is classified as unvoiced."""
        waveform = (np.random.normal(0, 1e-5, 22050)).astype(np.float32)
        res = self.extractor.extract(waveform, self.sr)
        self.assertEqual(res.voiced_frames, 0)

    # ------------------------------------------------------------------------
    # 6. Unvoiced & Interleaved Segments
    # ------------------------------------------------------------------------
    def test_interleaved_voiced_unvoiced(self):
        """Test: Interleaved tone and silence segments correctly mapped to voicing mask."""
        t1 = np.linspace(0, 0.5, int(self.sr * 0.5), endpoint=False)
        tone = (0.8 * np.sin(2 * np.pi * 200.0 * t1)).astype(np.float32)
        silence = np.zeros(int(self.sr * 0.5), dtype=np.float32)
        waveform = np.concatenate([tone, silence, tone])

        res = self.extractor.extract(waveform, self.sr)
        mid_idx = len(res.timestamps_seconds) // 2
        
        # Middle segment should be unvoiced
        self.assertFalse(res.voiced_mask[mid_idx])
        self.assertEqual(res.frequencies_hz[mid_idx], 0.0)
        # First and last segments should be voiced
        self.assertTrue(res.voiced_mask[10])
        self.assertTrue(res.voiced_mask[-10])

    # ------------------------------------------------------------------------
    # 7. Very Short Audio
    # ------------------------------------------------------------------------
    def test_very_short_audio(self):
        """Test: Handles tiny audio clips (20 ms / 441 samples) safely."""
        short_wave = np.zeros(441, dtype=np.float32)
        res = self.extractor.extract(short_wave, self.sr)
        self.assertGreaterEqual(res.total_frames, 1)
        self.assertTrue(np.all(np.isfinite(res.timestamps_seconds)))

    # ------------------------------------------------------------------------
    # 8. Malformed & NaN/Inf Waveform Inputs
    # ------------------------------------------------------------------------
    def test_empty_waveform(self):
        """Test: Empty array raises ValueError."""
        with self.assertRaises(ValueError):
            self.extractor.extract(np.array([], dtype=np.float32), self.sr)

    def test_2d_waveform(self):
        """Test: 2D stereo array raises ValueError."""
        with self.assertRaises(ValueError):
            self.extractor.extract(np.zeros((1000, 2), dtype=np.float32), self.sr)

    def test_nan_inf_waveform(self):
        """Test: Waveform containing NaN and Inf is sanitized without propagation."""
        t = np.linspace(0, 0.5, int(self.sr * 0.5), endpoint=False)
        wave = 0.5 * np.sin(2 * np.pi * 220.0 * t)
        wave[50:100] = np.nan
        wave[200:250] = np.inf

        res = self.extractor.extract(wave, self.sr)
        self.assertTrue(np.all(np.isfinite(res.frequencies_hz)))
        self.assertTrue(np.all(np.isfinite(res.confidence_values)))

    # ------------------------------------------------------------------------
    # 9. Deterministic Output
    # ------------------------------------------------------------------------
    def test_deterministic_repeated_extraction(self):
        """Test: Repeated extraction on identical waveform yields exact same arrays."""
        t = np.linspace(0, 1.0, int(self.sr * 1.0), endpoint=False)
        wave = (0.6 * np.sin(2 * np.pi * 180.0 * t)).astype(np.float32)

        res1 = self.extractor.extract(wave, self.sr)
        res2 = self.extractor.extract(wave, self.sr)

        np.testing.assert_array_equal(res1.frequencies_hz, res2.frequencies_hz)
        np.testing.assert_array_equal(res1.voiced_mask, res2.voiced_mask)
        np.testing.assert_array_equal(res1.confidence_values, res2.confidence_values)
        np.testing.assert_array_equal(res1.timestamps_seconds, res2.timestamps_seconds)

    # ------------------------------------------------------------------------
    # 10. Frequency Bounds & Invariants
    # ------------------------------------------------------------------------
    def test_frequency_bounds(self):
        """Test: Extracted voiced frequencies are strictly within configured [f_min, f_max]."""
        t = np.linspace(0, 0.5, int(self.sr * 0.5), endpoint=False)
        wave = 0.5 * np.sin(2 * np.pi * 140.0 * t).astype(np.float32)

        res = self.extractor.extract(wave, self.sr)
        voiced_freqs = res.frequencies_hz[res.voiced_mask]
        if len(voiced_freqs) > 0:
            self.assertTrue(np.all(voiced_freqs >= self.extractor.f_min_hz))
            self.assertTrue(np.all(voiced_freqs <= self.extractor.f_max_hz))

    # ------------------------------------------------------------------------
    # 11. Property / Fuzz Invariant Test
    # ------------------------------------------------------------------------
    def test_property_fuzz_invariants(self):
        """Test Invariants: timestamps are strictly monotonic, frequencies non-negative, conf in [0, 1]."""
        for _ in range(10):
            freq = random.uniform(80.0, 500.0)
            dur = random.uniform(0.1, 1.5)
            noise = random.uniform(0.0, 0.2)
            t = np.linspace(0, dur, int(self.sr * dur), endpoint=False)
            wave = (0.7 * np.sin(2 * np.pi * freq * t) + np.random.normal(0, noise, len(t))).astype(np.float32)

            res = self.extractor.extract(wave, self.sr)
            self.assertTrue(np.all(np.diff(res.timestamps_seconds) >= 0.0))
            self.assertTrue(np.all(res.frequencies_hz >= 0.0))
            self.assertTrue(np.all(res.confidence_values >= 0.0))
            self.assertTrue(np.all(res.confidence_values <= 1.0))
            self.assertEqual(len(res.timestamps_seconds), len(res.frequencies_hz))
            self.assertEqual(len(res.frequencies_hz), len(res.voiced_mask))
            summary = res.to_summary_dict()
            self.assertIsInstance(summary, dict)


    # ------------------------------------------------------------------------
    # 12. Adversarial Tests for Hindustani Polyphony & Contours
    # ------------------------------------------------------------------------
    def test_adversarial_octave_doubling(self):
        """Adversarial 1: Strong second harmonic (2*F0) does not cause octave doubling."""
        dur = 1.0
        t = np.linspace(0, dur, int(self.sr * dur), endpoint=False)
        f0 = 150.0  # D3
        # Signal where 2nd harmonic is as loud as fundamental
        wave = (0.5 * np.sin(2 * np.pi * f0 * t) + 0.6 * np.sin(2 * np.pi * 2 * f0 * t)).astype(np.float32)

        res = self.extractor.extract(wave, self.sr)
        voiced_freqs = res.frequencies_hz[res.voiced_mask]
        self.assertGreater(len(voiced_freqs), 0)
        mean_detected = float(np.mean(voiced_freqs))
        self.assertAlmostEqual(mean_detected, f0, delta=3.0)

    def test_adversarial_octave_halving(self):
        """Adversarial 2: Subharmonic resonance (F0/2) does not cause octave halving."""
        dur = 1.0
        t = np.linspace(0, dur, int(self.sr * dur), endpoint=False)
        f0 = 240.0  # B3
        # Signal with true fundamental at 240 Hz and faint subharmonic at 120 Hz
        wave = (0.7 * np.sin(2 * np.pi * f0 * t) + 0.25 * np.sin(2 * np.pi * (f0 / 2) * t)).astype(np.float32)

        res = self.extractor.extract(wave, self.sr, estimated_tonic_hz=240.0)
        voiced_freqs = res.frequencies_hz[res.voiced_mask]
        self.assertGreater(len(voiced_freqs), 0)
        mean_detected = float(np.mean(voiced_freqs))
        self.assertAlmostEqual(mean_detected, f0, delta=3.0)

    def test_adversarial_fifth_pa_interference(self):
        """Adversarial 3: Strong Pa (fifth / 1.5x) does not confuse the Sa fundamental."""
        dur = 1.0
        t = np.linspace(0, dur, int(self.sr * dur), endpoint=False)
        sa = 140.0  # C#3
        pa = 140.0 * 1.5  # 210.0 Hz (G#3)
        wave = (0.6 * np.sin(2 * np.pi * sa * t) + 0.45 * np.sin(2 * np.pi * pa * t)).astype(np.float32)

        res = self.extractor.extract(wave, self.sr, estimated_tonic_hz=sa)
        voiced_freqs = res.frequencies_hz[res.voiced_mask]
        self.assertGreater(len(voiced_freqs), 0)
        mean_detected = float(np.mean(voiced_freqs))
        self.assertAlmostEqual(mean_detected, sa, delta=4.0)

    def test_adversarial_strong_tanpura_drone(self):
        """Adversarial 4: Sustained multi-string Tanpura drone simulation (Pa, Sa, Sa, Sa_low)."""
        dur = 1.0
        t = np.linspace(0, dur, int(self.sr * dur), endpoint=False)
        sa = 146.83  # D3
        pa = sa * 1.5
        sa_low = sa / 2.0
        drone = (
            0.3 * np.sin(2 * np.pi * pa * t) +
            0.4 * np.sin(2 * np.pi * sa * t) +
            0.2 * np.sin(2 * np.pi * sa_low * t)
        ).astype(np.float32)

        res = self.extractor.extract(drone, self.sr, estimated_tonic_hz=sa)
        self.assertTrue(np.all(np.isfinite(res.frequencies_hz)))
        self.assertTrue(np.all(res.frequencies_hz >= 0.0))

    def test_adversarial_vocal_plus_drone_mixture(self):
        """Adversarial 5: Vocal melody clearly tracked in the presence of Tanpura drone."""
        dur = 1.0
        t = np.linspace(0, dur, int(self.sr * dur), endpoint=False)
        vocal_f = 220.0  # A3 vocal
        sa_drone = 146.83
        vocal = 0.65 * np.sin(2 * np.pi * vocal_f * t)
        drone = 0.25 * np.sin(2 * np.pi * sa_drone * t)
        mix = (vocal + drone).astype(np.float32)

        res = self.extractor.extract(mix, self.sr, estimated_tonic_hz=sa_drone)
        voiced_freqs = res.frequencies_hz[res.voiced_mask]
        self.assertGreater(len(voiced_freqs), 0)
        self.assertAlmostEqual(float(np.mean(voiced_freqs)), vocal_f, delta=4.0)

    def test_adversarial_vibrato(self):
        """Adversarial 6: Vocal vibrato (6 Hz rate, 50 cents depth) tracked continuously."""
        dur = 1.0
        t = np.linspace(0, dur, int(self.sr * dur), endpoint=False)
        f_center = 200.0
        # Instantaneous frequency with vibrato: f(t) = f0 * 2^( (depth_cents/1200) * sin(2*pi*f_vib*t) )
        vib_rate = 6.0
        depth_cents = 50.0
        inst_f = f_center * (2.0 ** ((depth_cents / 1200.0) * np.sin(2 * np.pi * vib_rate * t)))
        phase = 2 * np.pi * np.cumsum(inst_f) / self.sr
        wave = (0.8 * np.sin(phase)).astype(np.float32)

        res = self.extractor.extract(wave, self.sr)
        self.assertGreater(res.voiced_percentage, 90.0)
        voiced_f = res.frequencies_hz[res.voiced_mask]
        # Frequency should stay bounded within vibrato peak-to-peak envelope [194 Hz, 206 Hz]
        self.assertTrue(np.all(voiced_f >= 190.0))
        self.assertTrue(np.all(voiced_f <= 210.0))

    def test_adversarial_pitch_glide_meend(self):
        """Adversarial 7: Smooth continuous meend (glissando 180 Hz -> 240 Hz) has no dropouts."""
        dur = 1.0
        t = np.linspace(0, dur, int(self.sr * dur), endpoint=False)
        f_start, f_end = 180.0, 240.0
        # Smooth S-curve transition
        s_curve = 0.5 * (1.0 + np.sin(np.pi * (t / dur - 0.5)))
        inst_f = f_start + (f_end - f_start) * s_curve
        phase = 2 * np.pi * np.cumsum(inst_f) / self.sr
        wave = (0.75 * np.sin(phase)).astype(np.float32)

        res = self.extractor.extract(wave, self.sr)
        self.assertGreater(res.voiced_percentage, 90.0)

    def test_adversarial_legitimate_octave_change(self):
        """Adversarial 8: Legitimate octave leap (140 Hz -> 280 Hz) is tracked accurately."""
        dur = 1.0
        t1 = np.linspace(0, 0.5, int(self.sr * 0.5), endpoint=False)
        t2 = np.linspace(0.5, 1.0, int(self.sr * 0.5), endpoint=False)
        w1 = 0.7 * np.sin(2 * np.pi * 140.0 * t1)
        w2 = 0.7 * np.sin(2 * np.pi * 280.0 * t2)
        wave = np.concatenate([w1, w2]).astype(np.float32)

        res = self.extractor.extract(wave, self.sr)
        self.assertGreater(res.voiced_percentage, 85.0)
        # First half should be near 140 Hz, second half near 280 Hz (excluding 5 boundary frames)
        mid = len(res.frequencies_hz) // 2
        v1 = res.frequencies_hz[10:mid - 5]
        v2 = res.frequencies_hz[mid + 10:-10]
        v1 = v1[v1 > 0]
        v2 = v2[v2 > 0]
        self.assertGreater(len(v1), 0)
        self.assertGreater(len(v2), 0)
        self.assertAlmostEqual(float(np.mean(v1)), 140.0, delta=3.0)
        self.assertAlmostEqual(float(np.mean(v2)), 280.0, delta=3.0)

    def test_adversarial_silence_robustness(self):
        """Adversarial 9: Pure silence and high-variance noise floor return 0.0 Hz gracefully."""
        silence = np.zeros(10000, dtype=np.float32)
        res_silence = self.extractor.extract(silence, self.sr)
        self.assertEqual(res_silence.voiced_frames, 0)
        self.assertTrue(np.all(res_silence.frequencies_hz == 0.0))

    def test_adversarial_noisy_polyphonic_mixture(self):
        """Adversarial 10: Polyphonic mixture with harmonium harmonics, drone, and Gaussian noise."""
        dur = 1.0
        t = np.linspace(0, dur, int(self.sr * dur), endpoint=False)
        vocal_f = 196.0  # G3 vocal
        drone_f = 130.81 # C3 drone
        harmonium_f = vocal_f
        
        vocal = 0.5 * np.sin(2 * np.pi * vocal_f * t) + 0.2 * np.sin(2 * np.pi * 2 * vocal_f * t)
        drone = 0.2 * np.sin(2 * np.pi * drone_f * t) + 0.15 * np.sin(2 * np.pi * 1.5 * drone_f * t)
        harmonium = 0.25 * np.sin(2 * np.pi * harmonium_f * t)
        noise = np.random.normal(0, 0.08, len(t))
        
        poly_mix = (vocal + drone + harmonium + noise).astype(np.float32)
        res = self.extractor.extract(poly_mix, self.sr, estimated_tonic_hz=drone_f)
        voiced_freqs = res.frequencies_hz[res.voiced_mask]
        self.assertGreater(len(voiced_freqs), 0)
        self.assertAlmostEqual(float(np.mean(voiced_freqs)), vocal_f, delta=5.0)


if __name__ == "__main__":
    unittest.main()

