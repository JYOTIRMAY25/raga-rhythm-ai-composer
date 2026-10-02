"""
Comprehensive test suite for SwaraAnalyzer.

Tests:
1. Exact Sa (0 cents)
2. All 12 Swaras (Komal Re, Shuddha Re, Komal Ga, Shuddha Ga, Shuddha Ma, Tivra Ma,
   Pa, Komal Dha, Shuddha Dha, Komal Ni, Shuddha Ni)
3. Octave registers (Mandra, Madhya, Taar)
4. Ambiguous / boundary frequency handling (between two swaras)
5. Microtonal deviation tracking (cents_from_swara_center)
6. Vocal vibrato and oscillation stability
7. Continuous meend (glissando) ornament detection
8. Silence and unvoiced audio handling (safe NONE classification)
9. Malformed, empty, and NaN/Inf frequency inputs
10. Low-confidence / zero tonic fallback
11. Hysteresis anti-flicker smoothing
12. Pitch Class Distribution (PCD) mathematical invariants
13. Rapid swara transitions (bigrams)
14. Property and fuzz testing
"""

import math
import random
from typing import Any, Dict, List, Optional, Tuple, Union
import unittest

import numpy as np

from backend.app.analysis.pitch_extractor import PitchExtractionResult
from backend.app.analysis.swara_analyzer import (
    SwaraAnalyzer,
    SwaraAnalysisResult,
    SwaraSegment,
    SWARA_DEFINITIONS,
)
from backend.app.analysis.tonic_estimator import TonicEstimationResult


class TestSwaraAnalyzer(unittest.TestCase):
    """Test suite for SwaraAnalyzer."""

    def setUp(self):
        self.analyzer = SwaraAnalyzer()
        self.tonic_hz = 140.0  # C#3 typical Hindustani male vocal tonic

    def _create_mock_pitch_result(
        self,
        frequencies: np.ndarray,
        confidences: Optional[np.ndarray] = None,
        voiced_mask: Optional[np.ndarray] = None,
        frame_rate: float = 225.0,
    ) -> PitchExtractionResult:
        n = len(frequencies)
        ts = np.arange(n, dtype=np.float32) / frame_rate
        if confidences is None:
            confidences = np.where(frequencies > 0, 0.95, 0.0).astype(np.float32)
        if voiced_mask is None:
            voiced_mask = frequencies > 0.0
        return PitchExtractionResult(
            timestamps_seconds=ts,
            frequencies_hz=frequencies.astype(np.float32),
            voiced_mask=voiced_mask.astype(bool),
            confidence_values=confidences.astype(np.float32),
            frame_rate=frame_rate,
            method="mock_test",
        )

    # ------------------------------------------------------------------------
    # 1. Exact Sa (0 cents)
    # ------------------------------------------------------------------------
    def test_exact_sa(self):
        """Test: Maps exact tonic frequency (140.0 Hz) to Sa (S, shuddha, madhya)."""
        freqs = np.full(50, self.tonic_hz, dtype=np.float32)
        pitch_res = self._create_mock_pitch_result(freqs)

        res = self.analyzer.analyze(pitch_res, self.tonic_hz)

        self.assertEqual(res.swaras[0], "Sa")
        self.assertEqual(res.symbols[0], "S")
        self.assertEqual(res.variants[0], "shuddha")
        self.assertEqual(res.registers[0], "madhya")
        self.assertAlmostEqual(float(res.cents_from_tonic[0]), 0.0, delta=0.1)
        self.assertAlmostEqual(float(res.cents_from_swara_center[0]), 0.0, delta=0.1)
        self.assertGreater(res.swara_coverage_percentage, 95.0)
        self.assertGreater(len(res.segments), 0)
        self.assertEqual(res.segments[0].swara, "Sa")

    # ------------------------------------------------------------------------
    # 2. All 12 Canonical Swaras
    # ------------------------------------------------------------------------
    def test_all_12_canonical_swaras(self):
        """Test: Maps all 12 12-TET semitone ratios accurately to Indian swara names and symbols."""
        for swara_def in SWARA_DEFINITIONS:
            cents = swara_def["cents"]
            freq = self.tonic_hz * (2.0 ** (cents / 1200.0))
            freqs = np.full(30, freq, dtype=np.float32)
            pitch_res = self._create_mock_pitch_result(freqs)

            res = self.analyzer.analyze(pitch_res, self.tonic_hz)

            self.assertEqual(res.swaras[10], swara_def["name"], f"Failed for {swara_def}")
            self.assertEqual(res.symbols[10], swara_def["symbol"], f"Failed for {swara_def}")
            self.assertEqual(res.variants[10], swara_def["variant"], f"Failed for {swara_def}")
            self.assertEqual(res.registers[10], "madhya")
            self.assertAlmostEqual(float(res.cents_from_swara_center[10]), 0.0, delta=0.5)

    # ------------------------------------------------------------------------
    # 3. Komal Swaras
    # ------------------------------------------------------------------------
    def test_komal_swaras(self):
        """Test: Validates komal swaras (r, g, d, n) have variant='komal'."""
        komal_cents = [100.0, 300.0, 800.0, 1000.0]
        expected_symbols = ["r", "g", "d", "n"]
        expected_names = ["Re", "Ga", "Dha", "Ni"]

        for c, sym, name in zip(komal_cents, expected_symbols, expected_names):
            freq = self.tonic_hz * (2.0 ** (c / 1200.0))
            pitch_res = self._create_mock_pitch_result(np.full(20, freq, dtype=np.float32))
            res = self.analyzer.analyze(pitch_res, self.tonic_hz)

            self.assertEqual(res.symbols[5], sym)
            self.assertEqual(res.swaras[5], name)
            self.assertEqual(res.variants[5], "komal")

    # ------------------------------------------------------------------------
    # 4. Tivra Ma (M, 600 cents)
    # ------------------------------------------------------------------------
    def test_tivra_ma(self):
        """Test: Validates Tivra Madhyam (600 cents) maps to Ma, symbol 'M', variant 'tivra'."""
        tivra_ma_freq = self.tonic_hz * (2.0 ** (600.0 / 1200.0))
        pitch_res = self._create_mock_pitch_result(np.full(30, tivra_ma_freq, dtype=np.float32))

        res = self.analyzer.analyze(pitch_res, self.tonic_hz)
        self.assertEqual(res.swaras[10], "Ma")
        self.assertEqual(res.symbols[10], "M")
        self.assertEqual(res.variants[10], "tivra")

    # ------------------------------------------------------------------------
    # 5. Saptak Register / Octave Changes
    # ------------------------------------------------------------------------
    def test_saptak_registers(self):
        """Test: Identifies Mandra (lower), Madhya (middle), and Taar (upper) Saptak registers."""
        # Mandra Pa (-500 cents from Sa / 0.75 * Sa)
        mandra_pa = self.tonic_hz * (2.0 ** (-500.0 / 1200.0))
        # Madhya Pa (+700 cents)
        madhya_pa = self.tonic_hz * (2.0 ** (700.0 / 1200.0))
        # Taar Sa (+1200 cents)
        taar_sa = self.tonic_hz * 2.0
        # Taar Ga (+1600 cents)
        taar_ga = self.tonic_hz * (2.0 ** (1600.0 / 1200.0))

        for f, exp_reg, exp_sym in [
            (mandra_pa, "mandra", "P"),
            (madhya_pa, "madhya", "P"),
            (taar_sa, "taar", "S"),
            (taar_ga, "taar", "G"),
        ]:
            pitch_res = self._create_mock_pitch_result(np.full(20, f, dtype=np.float32))
            res = self.analyzer.analyze(pitch_res, self.tonic_hz)
            self.assertEqual(res.registers[5], exp_reg, f"Failed for {f} Hz")
            self.assertEqual(res.symbols[5], exp_sym, f"Failed symbol for {f} Hz")

    # ------------------------------------------------------------------------
    # 6. Ambiguous Frequency Boundary Handling
    # ------------------------------------------------------------------------
    def test_ambiguous_frequency_boundary(self):
        """Test: Frequency exactly on boundary (e.g. 50 cents) with low confidence is NONE."""
        boundary_f = self.tonic_hz * (2.0 ** (50.0 / 1200.0))  # Exactly between Sa (0) and Komal Re (100)
        # Low confidence (0.52 < 0.60) at boundary
        confs = np.full(20, 0.52, dtype=np.float32)
        pitch_res = self._create_mock_pitch_result(np.full(20, boundary_f, dtype=np.float32), confidences=confs)

        res = self.analyzer.analyze(pitch_res, self.tonic_hz)
        self.assertEqual(res.swaras[5], "NONE")
        self.assertEqual(res.symbols[5], "NONE")

    # ------------------------------------------------------------------------
    # 7. Microtonal Cents Deviation
    # ------------------------------------------------------------------------
    def test_microtonal_deviation_tracking(self):
        """Test: Accurately preserves microtonal shruti deviations (e.g. +18 cents)."""
        offset_cents = 18.0
        f = self.tonic_hz * (2.0 ** (offset_cents / 1200.0))
        pitch_res = self._create_mock_pitch_result(np.full(30, f, dtype=np.float32))

        res = self.analyzer.analyze(pitch_res, self.tonic_hz)
        self.assertEqual(res.symbols[10], "S")
        self.assertAlmostEqual(float(res.cents_from_swara_center[10]), offset_cents, delta=0.5)

    # ------------------------------------------------------------------------
    # 8. Vocal Vibrato / Gamak Stability
    # ------------------------------------------------------------------------
    def test_vibrato_oscillation_stability(self):
        """Test: Vocal vibrato (+/- 30 cents around Shuddha Ga) remains stable on Ga."""
        n_frames = 100
        t = np.arange(n_frames) / 225.0
        base_f = self.tonic_hz * (2.0 ** (400.0 / 1200.0))  # Shuddha Ga
        vib_cents = 30.0 * np.sin(2 * np.pi * 5.5 * t)
        freqs = base_f * (2.0 ** (vib_cents / 1200.0))

        pitch_res = self._create_mock_pitch_result(freqs)
        res = self.analyzer.analyze(pitch_res, self.tonic_hz)

        # All voiced frames should stay Ga (G)
        voiced_symbols = [s for s in res.symbols if s != "NONE"]
        self.assertGreater(len(voiced_symbols), 80)
        self.assertTrue(all(s == "G" for s in voiced_symbols))

    # ------------------------------------------------------------------------
    # 9. Continuous Meend (Glissando) Detection
    # ------------------------------------------------------------------------
    def test_meend_ornament_detection(self):
        """Test: Smooth glide from Sa (0c) to Ga (400c) is identified as a meend ornament."""
        n_frames = 60  # ~260 ms
        cents = np.linspace(0.0, 400.0, n_frames)
        freqs = self.tonic_hz * (2.0 ** (cents / 1200.0))

        pitch_res = self._create_mock_pitch_result(freqs)
        res = self.analyzer.analyze(pitch_res, self.tonic_hz)

        meends = [o for o in res.ornaments if o["type"] == "meend"]
        self.assertGreaterEqual(len(meends), 1)
        self.assertEqual(meends[0]["direction"], "ascending")
        self.assertGreaterEqual(meends[0]["interval_cents"], 300.0)

    # ------------------------------------------------------------------------
    # 10. Silence and Unvoiced Frames
    # ------------------------------------------------------------------------
    def test_silence_and_unvoiced_frames(self):
        """Test: All-zero or unvoiced input results in 0.0 coverage and all NONE swaras."""
        zeros = np.zeros(50, dtype=np.float32)
        pitch_res = self._create_mock_pitch_result(zeros)

        res = self.analyzer.analyze(pitch_res, self.tonic_hz)
        self.assertEqual(res.swara_coverage_percentage, 0.0)
        self.assertEqual(res.unvoiced_percentage, 100.0)
        self.assertTrue(all(s == "NONE" for s in res.swaras))
        self.assertTrue(all(s == "NONE" for s in res.symbols))
        self.assertEqual(len(res.segments), 0)

    # ------------------------------------------------------------------------
    # 11. Malformed and NaN/Inf Input
    # ------------------------------------------------------------------------
    def test_malformed_and_nan_inf_inputs(self):
        """Test: Arrays with NaN and Inf are handled cleanly without exceptions."""
        freqs = np.full(40, self.tonic_hz, dtype=np.float32)
        freqs[10:15] = np.nan
        freqs[20:25] = np.inf

        pitch_res = self._create_mock_pitch_result(freqs)
        res = self.analyzer.analyze(pitch_res, self.tonic_hz)

        self.assertEqual(len(res.swaras), 40)
        self.assertTrue(np.all(np.isfinite(res.cents_from_tonic)))
        self.assertTrue(np.all(np.isfinite(res.cents_from_swara_center)))

    # ------------------------------------------------------------------------
    # 12. Invalid / Zero Tonic Fallback
    # ------------------------------------------------------------------------
    def test_invalid_zero_tonic_fallback(self):
        """Test: Zero or negative tonic returns safe unvoiced result without crash."""
        freqs = np.full(30, 140.0, dtype=np.float32)
        pitch_res = self._create_mock_pitch_result(freqs)

        res_zero = self.analyzer.analyze(pitch_res, 0.0)
        self.assertEqual(res_zero.swara_coverage_percentage, 0.0)
        self.assertTrue(all(s == "NONE" for s in res_zero.swaras))

        res_neg = self.analyzer.analyze(pitch_res, -140.0)
        self.assertEqual(res_neg.swara_coverage_percentage, 0.0)

    # ------------------------------------------------------------------------
    # 13. Hysteresis Anti-Flicker
    # ------------------------------------------------------------------------
    def test_hysteresis_anti_flicker(self):
        """Test: 1-frame transient flicker is smoothed to maintain steady swara."""
        # 10 frames of Sa, 1 frame of Re glitch, 10 frames of Sa
        symbols = ["S"] * 10 + ["R"] + ["S"] * 10
        swaras = ["Sa"] * 10 + ["Re"] + ["Sa"] * 10
        variants = ["shuddha"] * 21
        registers = ["madhya"] * 21

        smoothed_sym, smoothed_swa, _, _ = self.analyzer._apply_hysteresis(symbols, swaras, variants, registers)
        self.assertEqual(smoothed_sym[10], "S")
        self.assertEqual(smoothed_swa[10], "Sa")

    # ------------------------------------------------------------------------
    # 14. Rapid Transitions & Bigrams
    # ------------------------------------------------------------------------
    def test_rapid_transitions_and_bigrams(self):
        """Test: Extracts valid ordered bigram transitions across swara sequence."""
        # Sa (10 frames) -> Re (10 frames) -> Ga (10 frames) -> Pa (10 frames)
        f_s = self.tonic_hz
        f_r = self.tonic_hz * (2.0 ** (200.0 / 1200.0))
        f_g = self.tonic_hz * (2.0 ** (400.0 / 1200.0))
        f_p = self.tonic_hz * (2.0 ** (700.0 / 1200.0))

        freqs = np.concatenate([np.full(10, f_s), np.full(10, f_r), np.full(10, f_g), np.full(10, f_p)])
        pitch_res = self._create_mock_pitch_result(freqs)

        res = self.analyzer.analyze(pitch_res, self.tonic_hz)
        self.assertGreaterEqual(len(res.segments), 4)
        self.assertIn(("S", "R"), res.transitions)
        self.assertIn(("R", "G"), res.transitions)
        self.assertIn(("G", "P"), res.transitions)

    # ------------------------------------------------------------------------
    # 15. Pitch Class Distribution (PCD) Mathematical Invariants
    # ------------------------------------------------------------------------
    def test_pcd_mathematical_invariants(self):
        """Test: PCD values are non-negative and sum to 1.0 for voiced audio."""
        f_s = self.tonic_hz
        f_p = self.tonic_hz * (2.0 ** (700.0 / 1200.0))
        freqs = np.concatenate([np.full(30, f_s), np.full(10, f_p)])
        pitch_res = self._create_mock_pitch_result(freqs)

        res = self.analyzer.analyze(pitch_res, self.tonic_hz)
        pcd = res.pitch_class_distribution

        self.assertEqual(len(pcd), 12)
        self.assertTrue(all(v >= 0.0 for v in pcd.values()))
        self.assertAlmostEqual(sum(pcd.values()), 1.0, places=4)
        self.assertGreater(pcd["S"], pcd["P"])
        self.assertEqual(res.dominant_swaras[0][0], "S")

    # ------------------------------------------------------------------------
    # 16. Property / Fuzz Testing
    # ------------------------------------------------------------------------
    def test_property_fuzz_invariants(self):
        """Test Fuzz: Random pitch and confidence vectors strictly obey data structure invariants."""
        for _ in range(15):
            n = random.randint(10, 150)
            freqs = np.random.uniform(70.0, 500.0, n).astype(np.float32)
            confs = np.random.uniform(0.0, 1.0, n).astype(np.float32)
            tonic = random.uniform(100.0, 260.0)

            pitch_res = self._create_mock_pitch_result(freqs, confidences=confs)
            res = self.analyzer.analyze(pitch_res, tonic)

            self.assertEqual(len(res.swaras), n)
            self.assertEqual(len(res.symbols), n)
            self.assertEqual(len(res.variants), n)
            self.assertEqual(len(res.registers), n)
            self.assertTrue(np.all(np.isfinite(res.cents_from_tonic)))
            self.assertTrue(np.all(np.isfinite(res.cents_from_swara_center)))
            self.assertTrue(0.0 <= res.swara_coverage_percentage <= 100.0)
            self.assertTrue(0.0 <= res.unvoiced_percentage <= 100.0)
            self.assertIsInstance(res.to_summary_dict(), dict)


if __name__ == "__main__":
    unittest.main()
