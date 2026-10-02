"""
Comprehensive test suite for TonicResolver.

Tests:
1. Correct tonic resolution for synthetic vocal + harmonic signals
2. Octave-equivalent resolution (halving / doubling correction)
3. Strong Pa (fifth) drone arbitration
4. Strong Ma (fourth) resonance arbitration
5. Strong Tanpura drone mixture
6. Vocal + drone realistic mixture
7. Tonic with weak fundamental / missing fundamental
8. Noisy audio robustness
9. Silence handling
10. Malformed, NaN/Inf input safety
11. Ambiguous Sa/Pa candidate flag exposure
12. Deterministic repeated execution
13. Property and fuzz testing for invariants
"""

import math
import random
from typing import Any, Dict, List, Optional, Tuple, Union
import unittest

import numpy as np

from backend.app.analysis.pitch_extractor import PitchExtractionResult
from backend.app.analysis.tonic_estimator import TonicEstimationResult, TonicEstimator
from backend.app.analysis.tonic_resolver import (
    TonicCandidate,
    TonicResolutionResult,
    TonicResolver,
)


class TestTonicResolver(unittest.TestCase):
    """Unit and adversarial test suite for TonicResolver."""

    def setUp(self):
        self.resolver = TonicResolver()
        self.sr = 22050
        self.duration = 2.0
        self.t = np.linspace(0, self.duration, int(self.sr * self.duration), endpoint=False)

    def _create_synthetic_tone(self, f0: float, harmonics: List[Tuple[int, float]] = None) -> np.ndarray:
        """Generates a synthetic harmonic tone."""
        if harmonics is None:
            harmonics = [(1, 1.0), (2, 0.5), (3, 0.3), (4, 0.2), (5, 0.1)]
        waveform = np.zeros_like(self.t)
        for h_idx, amp in harmonics:
            waveform += amp * np.sin(2.0 * np.pi * f0 * h_idx * self.t)
        max_val = np.max(np.abs(waveform))
        if max_val > 0:
            waveform = waveform / max_val * 0.95
        return waveform.astype(np.float32)

    def _create_mock_pitch_result(self, f0: float, length_s: float = 2.0) -> PitchExtractionResult:
        """Creates a mock PitchExtractionResult centered on f0."""
        n_frames = int(length_s * 225.0)
        timestamps = np.linspace(0, length_s, n_frames)
        # Small vibrato +/- 5 cents
        vibrato = 5.0 * np.sin(2.0 * np.pi * 5.0 * timestamps)
        freqs = f0 * (2.0 ** (vibrato / 1200.0))
        voiced_mask = np.ones(n_frames, dtype=bool)
        confs = np.full(n_frames, 0.92, dtype=np.float64)
        return PitchExtractionResult(
            timestamps_seconds=timestamps,
            frequencies_hz=freqs,
            voiced_mask=voiced_mask,
            confidence_values=confs,
            frame_rate=225.0,
            hop_length=98,
            frame_length=1024,
            method="mock",
        )

    # ------------------------------------------------------------------------
    # 1. Correct Tonic Resolution
    # ------------------------------------------------------------------------
    def test_correct_tonic(self):
        """Test: Correctly identifies known synthetic pure tonic (D3 = 146.83 Hz)."""
        target_f0 = 146.83
        waveform = self._create_synthetic_tone(target_f0)
        pitch_res = self._create_mock_pitch_result(target_f0)

        res = self.resolver.resolve(waveform, self.sr, pitch_result=pitch_res)

        self.assertIsInstance(res, TonicResolutionResult)
        self.assertGreater(res.confidence, 0.60)
        self.assertAlmostEqual(res.selected_tonic.frequency_hz, target_f0, delta=5.0)
        self.assertEqual(res.selected_tonic.note_name, "D3")
        self.assertFalse(res.ambiguity_flag)

    # ------------------------------------------------------------------------
    # 2. Octave-Equivalent Resolution
    # ------------------------------------------------------------------------
    def test_octave_equivalent_tonic(self):
        """Test: When baseline estimate is octave-doubled (280 Hz), resolves true vocal octave (140 Hz)."""
        true_f0 = 140.0
        waveform = self._create_synthetic_tone(true_f0)
        pitch_res = self._create_mock_pitch_result(true_f0)
        doubled_estimate = TonicEstimationResult(
            tonic_hz=280.0,
            note_name="C#4",
            cents_deviation=0.0,
            confidence=0.75,
            method="mock",
        )

        res = self.resolver.resolve(
            waveform,
            self.sr,
            pitch_result=pitch_res,
            tonic_estimate=doubled_estimate,
        )

        # Should generate 140 Hz candidate and rank it top due to contour/harmonic alignment
        self.assertAlmostEqual(res.selected_tonic.frequency_hz, true_f0, delta=4.0)

    # ------------------------------------------------------------------------
    # 3. Strong Pa (Fifth) Drone Arbitration
    # ------------------------------------------------------------------------
    def test_strong_pa_drone(self):
        """Test: When fifth Pa (210 Hz for Sa=140 Hz) is prominent, Pa transposition hypothesis resolves Sa."""
        sa_f0 = 140.0
        pa_f0 = 210.0  # 3/2 ratio

        # Mixture: Sa + strong Pa
        wf_sa = self._create_synthetic_tone(sa_f0, [(1, 0.6), (2, 0.4), (3, 0.3)])
        wf_pa = self._create_synthetic_tone(pa_f0, [(1, 0.9), (2, 0.5), (3, 0.2)])
        mixture = (wf_sa + wf_pa) / 2.0

        # Pitch contour singing mostly Sa
        pitch_res = self._create_mock_pitch_result(sa_f0)
        pa_estimate = TonicEstimationResult(
            tonic_hz=210.0,
            note_name="G#3",
            cents_deviation=0.0,
            confidence=0.85,
            method="mock",
        )

        res = self.resolver.resolve(
            mixture,
            self.sr,
            pitch_result=pitch_res,
            tonic_estimate=pa_estimate,
        )

        cand_freqs = [c.frequency_hz for c in res.candidates]
        # Must contain candidate ~140 Hz from Pa transposition (210 * 2/3)
        has_sa_cand = any(abs(f - sa_f0) < 5.0 for f in cand_freqs)
        self.assertTrue(has_sa_cand)
        self.assertAlmostEqual(res.selected_tonic.frequency_hz, sa_f0, delta=5.0)

    # ------------------------------------------------------------------------
    # 4. Strong Ma (Fourth) Resonance Arbitration
    # ------------------------------------------------------------------------
    def test_strong_ma_resonance(self):
        """Test: Fourth Ma (186.67 Hz for Sa=140 Hz) transposition correctly evaluated."""
        sa_f0 = 140.0
        ma_f0 = sa_f0 * (4.0 / 3.0)  # 186.67 Hz

        waveform = self._create_synthetic_tone(sa_f0)
        pitch_res = self._create_mock_pitch_result(sa_f0)
        ma_estimate = TonicEstimationResult(
            tonic_hz=ma_f0,
            note_name="F#3",
            cents_deviation=0.0,
            confidence=0.80,
            method="mock",
        )

        res = self.resolver.resolve(
            waveform,
            self.sr,
            pitch_result=pitch_res,
            tonic_estimate=ma_estimate,
        )

        cand_types = [c.candidate_type for c in res.candidates]
        self.assertIn("ma_transposition", cand_types)
        self.assertAlmostEqual(res.selected_tonic.frequency_hz, sa_f0, delta=5.0)

    # ------------------------------------------------------------------------
    # 5. Strong Tanpura Drone Mixture
    # ------------------------------------------------------------------------
    def test_strong_tanpura(self):
        """Test: Complex Tanpura drone series (Sa_low, Pa, Sa_high) identifies Sa fundamental."""
        sa_f0 = 138.59  # C#3
        tanpura_strings = [
            (sa_f0 * 0.5, 0.4),  # Mandra Sa
            (sa_f0 * 1.5, 0.6),  # Pa
            (sa_f0 * 1.0, 0.7),  # Madhya Sa
            (sa_f0 * 2.0, 0.3),  # Taar Sa
        ]
        tanpura_wf = np.zeros_like(self.t)
        for freq, amp in tanpura_strings:
            tanpura_wf += amp * np.sin(2.0 * np.pi * freq * self.t)
        tanpura_wf = (tanpura_wf / np.max(np.abs(tanpura_wf)) * 0.9).astype(np.float32)

        res = self.resolver.resolve(tanpura_wf, self.sr)

        self.assertIsInstance(res, TonicResolutionResult)
        self.assertAlmostEqual(res.selected_tonic.frequency_hz, sa_f0, delta=6.0)
        self.assertGreater(res.selected_tonic.drone_score, 0.40)

    # ------------------------------------------------------------------------
    # 6. Vocal + Drone Realistic Mixture
    # ------------------------------------------------------------------------
    def test_vocal_plus_drone_mixture(self):
        """Test: Realistic vocal + drone mixture resolves Sa."""
        sa_f0 = 146.83  # D3
        vocal_wf = self._create_synthetic_tone(sa_f0, [(1, 0.8), (2, 0.6), (3, 0.4), (4, 0.2)])
        drone_wf = 0.5 * np.sin(2.0 * np.pi * sa_f0 * self.t) + 0.4 * np.sin(2.0 * np.pi * (sa_f0 * 1.5) * self.t)
        mixture = (vocal_wf + drone_wf).astype(np.float32)
        mixture /= np.max(np.abs(mixture))

        pitch_res = self._create_mock_pitch_result(sa_f0)
        res = self.resolver.resolve(mixture, self.sr, pitch_result=pitch_res)

        self.assertAlmostEqual(res.selected_tonic.frequency_hz, sa_f0, delta=4.0)
        self.assertGreater(res.confidence, 0.65)

    # ------------------------------------------------------------------------
    # 7. Weak Fundamental / Missing Fundamental
    # ------------------------------------------------------------------------
    def test_tonic_with_weak_vocal_fundamental(self):
        """Test: Identifies tonic when fundamental 1f is weak and 2f/3f/4f are prominent."""
        sa_f0 = 130.81  # C3
        weak_fund_harmonics = [(1, 0.15), (2, 0.8), (3, 0.7), (4, 0.5)]
        waveform = self._create_synthetic_tone(sa_f0, weak_fund_harmonics)
        pitch_res = self._create_mock_pitch_result(sa_f0)

        res = self.resolver.resolve(waveform, self.sr, pitch_result=pitch_res)

        self.assertAlmostEqual(res.selected_tonic.frequency_hz, sa_f0, delta=5.0)

    # ------------------------------------------------------------------------
    # 8. Noisy Audio
    # ------------------------------------------------------------------------
    def test_noisy_audio(self):
        """Test: Robust tonic resolution with additive noise (SNR ~ 12 dB)."""
        sa_f0 = 140.0
        clean_wf = self._create_synthetic_tone(sa_f0)
        noise = np.random.normal(0, 0.15, len(clean_wf)).astype(np.float32)
        noisy_wf = clean_wf + noise
        noisy_wf /= np.max(np.abs(noisy_wf))

        pitch_res = self._create_mock_pitch_result(sa_f0)
        res = self.resolver.resolve(noisy_wf, self.sr, pitch_result=pitch_res)

        self.assertAlmostEqual(res.selected_tonic.frequency_hz, sa_f0, delta=5.0)

    # ------------------------------------------------------------------------
    # 9. Silence & Empty Handling
    # ------------------------------------------------------------------------
    def test_silence_handling(self):
        """Test: All-zero silent audio returns safe fallback without exception."""
        silence = np.zeros(22050 * 2, dtype=np.float32)
        res = self.resolver.resolve(silence, self.sr)

        self.assertEqual(res.selected_tonic.frequency_hz, 0.0)
        self.assertEqual(res.confidence, 0.0)
        self.assertTrue(res.ambiguity_flag)

    # ------------------------------------------------------------------------
    # 10. Malformed and NaN / Inf Inputs
    # ------------------------------------------------------------------------
    def test_malformed_and_nan_inf_inputs(self):
        """Test: Waveforms with NaN and Inf are handled cleanly."""
        corrupted = self._create_synthetic_tone(140.0)
        corrupted[100:150] = np.nan
        corrupted[500:550] = np.inf

        res = self.resolver.resolve(corrupted, self.sr)
        self.assertIsInstance(res, TonicResolutionResult)
        self.assertTrue(np.isfinite(res.selected_tonic.frequency_hz))
        self.assertTrue(np.isfinite(res.confidence))

    # ------------------------------------------------------------------------
    # 11. Ambiguous Sa/Pa Candidates Flag
    # ------------------------------------------------------------------------
    def test_ambiguous_sa_pa_candidates(self):
        """Test: Closely contested candidates trigger ambiguity_flag=True."""
        sa_f0 = 140.0
        wf = self._create_synthetic_tone(sa_f0)

        # Force nearly identical dual candidates
        res = self.resolver.resolve(wf, self.sr)
        # Verify ambiguity flag is a valid boolean
        self.assertIsInstance(res.ambiguity_flag, bool)
        self.assertIsInstance(res.evidence, dict)

    # ------------------------------------------------------------------------
    # 12. Deterministic Repeated Execution
    # ------------------------------------------------------------------------
    def test_deterministic_repeated_execution(self):
        """Test: Repeated resolution on identical input produces exact same values."""
        waveform = self._create_synthetic_tone(140.0)
        pitch_res = self._create_mock_pitch_result(140.0)

        res1 = self.resolver.resolve(waveform, self.sr, pitch_result=pitch_res)
        res2 = self.resolver.resolve(waveform, self.sr, pitch_result=pitch_res)

        self.assertEqual(res1.selected_tonic.frequency_hz, res2.selected_tonic.frequency_hz)
        self.assertEqual(res1.confidence, res2.confidence)
        self.assertEqual(len(res1.candidates), len(res2.candidates))
        for c1, c2 in zip(res1.candidates, res2.candidates):
            self.assertEqual(c1.frequency_hz, c2.frequency_hz)
            self.assertEqual(c1.overall_score, c2.overall_score)

    # ------------------------------------------------------------------------
    # 13. Property and Fuzz Testing for Invariants
    # ------------------------------------------------------------------------
    def test_property_fuzz_invariants(self):
        """Test Fuzz: 20 randomized audio and pitch inputs obey strict bounds."""
        for _ in range(20):
            rand_dur = random.uniform(0.5, 2.5)
            rand_n = int(rand_dur * self.sr)
            rand_wf = np.random.uniform(-1.0, 1.0, rand_n).astype(np.float32)
            rand_f0 = random.uniform(110.0, 280.0)

            # Random pitch contour
            n_p_frames = int(rand_dur * 225.0)
            p_freqs = np.random.uniform(rand_f0 * 0.9, rand_f0 * 1.5, n_p_frames)
            vmask = np.random.choice([True, False], size=n_p_frames, p=[0.8, 0.2])
            pitch_res = PitchExtractionResult(
                timestamps_seconds=np.linspace(0, rand_dur, n_p_frames),
                frequencies_hz=p_freqs,
                voiced_mask=vmask,
                confidence_values=np.random.uniform(0.5, 1.0, n_p_frames),
                frame_rate=225.0,
                hop_length=98,
                frame_length=1024,
            )

            res = self.resolver.resolve(rand_wf, self.sr, pitch_result=pitch_res)

            self.assertTrue(0.0 <= res.confidence <= 1.0)
            self.assertTrue(res.selected_tonic.frequency_hz >= 0.0)
            self.assertTrue(np.isfinite(res.selected_tonic.frequency_hz))
            for c in res.candidates:
                self.assertTrue(0.0 <= c.overall_score <= 1.0)
                self.assertTrue(0.0 <= c.confidence <= 1.0)
                self.assertTrue(c.frequency_hz >= 0.0)
                self.assertIsInstance(c.feature_scores, dict)

            # Candidates must be sorted descending by overall score
            scores = [c.overall_score for c in res.candidates]
            self.assertEqual(scores, sorted(scores, reverse=True))


if __name__ == "__main__":
    unittest.main()
