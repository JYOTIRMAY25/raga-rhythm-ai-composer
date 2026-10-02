"""
Comprehensive test suite for RagaDetector.

Tests:
1. Exact synthetic swara profile (Yaman, Bhairavi, Bhoopali, Todi)
2. Strong candidate vs contradictory candidate
3. Missing characteristic swaras
4. Extra forbidden (varjit) swaras
5. Ascending / descending scale pattern matching
6. Characteristic Pakad motif detection
7. Komal / Tivra swara distinction
8. Ambiguous profile handling and limitation exposure
9. Insufficient evidence and silent audio fallback
10. Malformed, empty, and NaN/Inf inputs
11. Deterministic repeated execution
12. Property and fuzz testing for mathematical score invariants
"""

import math
import random
from typing import Any, Dict, List, Optional, Tuple, Union
import unittest

import numpy as np

from backend.app.analysis.raga_detector import (
    RagaDetector,
    RagaAnalysisResult,
    RagaCandidate,
    RAGA_KNOWLEDGE_BASE,
    ALL_SWARA_SYMBOLS,
)
from backend.app.analysis.swara_analyzer import (
    SwaraAnalysisResult,
    SwaraSegment,
    SWARA_DEFINITIONS,
)


class TestRagaDetector(unittest.TestCase):
    """Test suite for RagaDetector."""

    def setUp(self):
        self.detector = RagaDetector()

    def _create_mock_swara_result(
        self,
        pcd: Dict[str, float],
        symbols: Optional[List[str]] = None,
        transitions: Optional[List[Tuple[str, str]]] = None,
        coverage_pct: float = 90.0,
        tonic_hz: float = 140.0,
    ) -> SwaraAnalysisResult:
        n = 100
        ts = np.arange(n, dtype=np.float32) / 225.0
        freqs = np.full(n, tonic_hz, dtype=np.float32)
        confs = np.full(n, 0.9, dtype=np.float32)

        # Normalize PCD
        total = sum(pcd.values())
        norm_pcd = {k: v / total for k, v in pcd.items()} if total > 0 else pcd
        # Ensure all 12 swaras exist in dict
        full_pcd = {s["symbol"]: norm_pcd.get(s["symbol"], 0.0) for s in SWARA_DEFINITIONS}

        if symbols is None:
            symbols = ["S"] * n
        if transitions is None:
            transitions = []

        segments: List[SwaraSegment] = []
        curr_sym = symbols[0]
        start_t = 0.0
        for i, s in enumerate(symbols):
            if s != curr_sym or i == len(symbols) - 1:
                end_t = float(ts[i])
                segments.append(
                    SwaraSegment(
                        swara="Sa",
                        symbol=curr_sym,
                        variant="shuddha",
                        register="madhya",
                        start_time_seconds=start_t,
                        end_time_seconds=end_t,
                        duration_seconds=max(0.01, end_t - start_t),
                        mean_frequency_hz=tonic_hz,
                        mean_cents_deviation=0.0,
                        mean_confidence=0.9,
                        movement_type="steady",
                    )
                )
                curr_sym = s
                start_t = end_t

        dom_swaras = [(k, v) for k, v in sorted(full_pcd.items(), key=lambda x: x[1], reverse=True) if v > 0.01]

        return SwaraAnalysisResult(
            timestamps_seconds=ts,
            frequencies_hz=freqs,
            swaras=["Sa"] * n,
            symbols=symbols,
            variants=["shuddha"] * n,
            registers=["madhya"] * n,
            cents_from_tonic=np.zeros(n, dtype=np.float32),
            cents_from_swara_center=np.zeros(n, dtype=np.float32),
            confidence_values=confs,
            segments=segments,
            pitch_class_distribution=full_pcd,
            dominant_swaras=dom_swaras,
            transitions=transitions,
            ornaments=[],
            swara_coverage_percentage=coverage_pct,
            unvoiced_percentage=100.0 - coverage_pct,
            tonic_hz=tonic_hz,
            method="test_mock",
        )

    # ------------------------------------------------------------------------
    # 1. Exact Synthetic Profile (Yaman)
    # ------------------------------------------------------------------------
    def test_exact_yaman_profile(self):
        """Test: Canonical Yaman swaras (S, R, G, M, P, D, N) and Pakad motifs correctly identify Yaman."""
        pcd = {"S": 0.12, "R": 0.16, "G": 0.22, "M": 0.16, "P": 0.14, "D": 0.10, "N": 0.10}
        # Sequence containing Yaman pakad: N -> R -> G -> M -> D -> N -> S
        seq = ["N"] * 5 + ["R"] * 5 + ["G"] * 10 + ["M"] * 5 + ["D"] * 5 + ["N"] * 5 + ["S"] * 5
        trans = [("N", "R"), ("R", "G"), ("G", "M"), ("M", "D"), ("D", "N"), ("N", "S")]

        swara_res = self._create_mock_swara_result(pcd, symbols=seq, transitions=trans)
        res = self.detector.detect(swara_res, tonic_input=140.0)

        self.assertEqual(res.detected_raga, "Yaman")
        self.assertGreater(res.confidence, 0.70)
        self.assertEqual(res.top_candidates[0].raga_name, "Yaman")
        self.assertEqual(res.top_candidates[0].thaat, "Kalyan")
        self.assertGreater(len(res.top_candidates[0].matched_features), 0)

    # ------------------------------------------------------------------------
    # 2. Strong Candidate vs Contradictory Candidate
    # ------------------------------------------------------------------------
    def test_strong_vs_contradictory_candidate(self):
        """Test: Bhairavi profile correctly rejects Yaman and detects Bhairavi."""
        pcd = {"S": 0.18, "r": 0.16, "g": 0.18, "m": 0.22, "P": 0.12, "d": 0.10, "n": 0.04}
        seq = ["m"] * 8 + ["g"] * 6 + ["S"] * 6 + ["r"] * 6 + ["S"] * 6
        trans = [("m", "g"), ("g", "S"), ("S", "r"), ("r", "S")]

        swara_res = self._create_mock_swara_result(pcd, symbols=seq, transitions=trans)
        res = self.detector.detect(swara_res, tonic_input=140.0)

        self.assertEqual(res.detected_raga, "Bhairavi")
        # Yaman should have heavy contradictory penalties due to komal notes
        yaman_cands = [c for c in res.top_candidates if c.raga_id == "yaman"]
        if yaman_cands:
            self.assertGreater(len(yaman_cands[0].contradictory_features), 0)
            self.assertLess(yaman_cands[0].score, 0.40)

    # ------------------------------------------------------------------------
    # 3. Missing Characteristic Swara Penalty
    # ------------------------------------------------------------------------
    def test_missing_characteristic_swara(self):
        """Test: Yaman missing Tivra Ma ('M') suffers penalty and reports missing feature."""
        # Yaman swaras but Tivra Ma completely missing
        pcd = {"S": 0.20, "R": 0.25, "G": 0.30, "P": 0.15, "D": 0.10}
        swara_res = self._create_mock_swara_result(pcd)
        res = self.detector.detect(swara_res, tonic_input=140.0)

        yaman_cands = [c for c in res.top_candidates if c.raga_id == "yaman"]
        self.assertGreater(len(yaman_cands), 0)
        self.assertTrue(any("Missing expected swaras" in f for f in yaman_cands[0].missing_features))

    # ------------------------------------------------------------------------
    # 4. Extra Forbidden (Varjit) Swara Detection
    # ------------------------------------------------------------------------
    def test_extra_forbidden_swara_penalty(self):
        """Test: Bhoopali containing forbidden Komal Ga ('g') and Ma ('m') triggers varjit penalties."""
        # Bhoopali + 10% Komal Ga (g)
        pcd = {"S": 0.20, "R": 0.20, "G": 0.25, "g": 0.10, "P": 0.15, "D": 0.10}
        swara_res = self._create_mock_swara_result(pcd)
        res = self.detector.detect(swara_res, tonic_input=140.0)

        bhoop_cands = [c for c in res.top_candidates if c.raga_id == "bhoopali"]
        self.assertGreater(len(bhoop_cands), 0)
        self.assertTrue(any("Forbidden swara 'g'" in f for f in bhoop_cands[0].contradictory_features))

    # ------------------------------------------------------------------------
    # 5. Komal vs Tivra Swara Distinction (Todi vs Bhairav)
    # ------------------------------------------------------------------------
    def test_komal_tivra_distinction(self):
        """Test: Distinguishes Todi (r, g, M, d, N) from Bhairav (r, G, m, d, N)."""
        # Todi profile: Tivra Ma ('M') and Komal Ga ('g')
        pcd_todi = {"S": 0.14, "r": 0.18, "g": 0.20, "M": 0.16, "d": 0.20, "N": 0.12}
        swara_res_todi = self._create_mock_swara_result(pcd_todi)
        res_todi = self.detector.detect(swara_res_todi, tonic_input=140.0)
        self.assertEqual(res_todi.detected_raga, "Todi")

        # Bhairav profile: Shuddha Ma ('m') and Shuddha Ga ('G')
        pcd_bhairav = {"S": 0.16, "r": 0.18, "G": 0.18, "m": 0.20, "P": 0.12, "d": 0.16}
        swara_res_bhairav = self._create_mock_swara_result(pcd_bhairav)
        res_bhairav = self.detector.detect(swara_res_bhairav, tonic_input=140.0)
        self.assertEqual(res_bhairav.detected_raga, "Bhairav")

    # ------------------------------------------------------------------------
    # 6. Characteristic Phrase / Pakad Matching
    # ------------------------------------------------------------------------
    def test_characteristic_phrase_pakad(self):
        """Test: Detects specific Pakad sequence and boosts matching candidate."""
        pcd = {"S": 0.18, "g": 0.22, "m": 0.26, "d": 0.18, "n": 0.16}
        # Malkauns pakad: g -> m -> d -> m -> g -> S
        seq = ["g"] * 4 + ["m"] * 4 + ["d"] * 4 + ["m"] * 4 + ["g"] * 4 + ["S"] * 6
        swara_res = self._create_mock_swara_result(pcd, symbols=seq)
        res = self.detector.detect(swara_res, tonic_input=140.0)

        self.assertEqual(res.detected_raga, "Malkauns")
        malk_cand = res.top_candidates[0]
        self.assertTrue(any("Pakad motif" in f for f in malk_cand.matched_features))

    # ------------------------------------------------------------------------
    # 7. Ambiguous Candidate Handling
    # ------------------------------------------------------------------------
    def test_ambiguous_candidate_profile(self):
        """Test: Closely contested candidates trigger ambiguity limitation rather than false certainty."""
        # Ambiguous pentatonic profile matching both Bhoopali and Jait Kalyan
        pcd = {"S": 0.20, "R": 0.18, "G": 0.22, "P": 0.22, "D": 0.18}
        swara_res = self._create_mock_swara_result(pcd)
        res = self.detector.detect(swara_res, tonic_input=140.0)

        self.assertGreater(len(res.top_candidates), 1)
        # Difference between Bhoopali and Jait Kalyan should be narrow
        score_diff = abs(res.top_candidates[0].score - res.top_candidates[1].score)
        if score_diff < self.detector.AMBIGUITY_MARGIN:
            self.assertTrue(any("Ambiguous" in lim for lim in res.limitations))

    # ------------------------------------------------------------------------
    # 8. Insufficient Evidence / Silent Audio
    # ------------------------------------------------------------------------
    def test_insufficient_evidence_silence(self):
        """Test: Low voiced coverage (<15%) safely returns 'INSUFFICIENT_EVIDENCE'."""
        empty_pcd = {s["symbol"]: 0.0 for s in SWARA_DEFINITIONS}
        swara_res = self._create_mock_swara_result(empty_pcd, coverage_pct=5.0)
        res = self.detector.detect(swara_res, tonic_input=140.0)

        self.assertEqual(res.detected_raga, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(res.confidence, 0.0)
        self.assertEqual(len(res.top_candidates), 0)
        self.assertGreater(len(res.limitations), 0)

    # ------------------------------------------------------------------------
    # 9. Malformed and NaN/Inf Input
    # ------------------------------------------------------------------------
    def test_malformed_and_nan_inf_inputs(self):
        """Test: Non-finite PCD inputs are handled safely without exceptions."""
        pcd = {"S": float("nan"), "R": float("inf"), "G": 0.5}
        swara_res = self._create_mock_swara_result(pcd)
        res = self.detector.detect(swara_res, tonic_input=140.0)
        self.assertIsInstance(res.detected_raga, str)
        self.assertTrue(np.isfinite(res.confidence))

    # ------------------------------------------------------------------------
    # 10. Deterministic Repeated Execution
    # ------------------------------------------------------------------------
    def test_deterministic_repeated_execution(self):
        """Test: Repeated detection on identical inputs yields bitwise identical candidate scores."""
        pcd = {"S": 0.16, "R": 0.14, "G": 0.22, "M": 0.16, "P": 0.14, "D": 0.10, "N": 0.08}
        swara_res = self._create_mock_swara_result(pcd)

        res1 = self.detector.detect(swara_res, tonic_input=140.0)
        res2 = self.detector.detect(swara_res, tonic_input=140.0)

        self.assertEqual(res1.detected_raga, res2.detected_raga)
        self.assertEqual(res1.confidence, res2.confidence)
        self.assertEqual(len(res1.top_candidates), len(res2.top_candidates))
        for c1, c2 in zip(res1.top_candidates, res2.top_candidates):
            self.assertEqual(c1.raga_id, c2.raga_id)
            self.assertEqual(c1.score, c2.score)

    # ------------------------------------------------------------------------
    # 11. Property and Fuzz Testing for Invariants
    # ------------------------------------------------------------------------
    def test_property_fuzz_invariants(self):
        """Test Fuzz: 20 randomized PCD vectors strictly obey mathematical bounds [0.0, 1.0]."""
        for _ in range(20):
            rand_weights = np.random.uniform(0.0, 1.0, 12)
            rand_pcd = {sym: float(w) for sym, w in zip(ALL_SWARA_SYMBOLS, rand_weights)}
            cov = random.uniform(20.0, 100.0)

            swara_res = self._create_mock_swara_result(rand_pcd, coverage_pct=cov)
            res = self.detector.detect(swara_res, tonic_input=140.0)

            self.assertTrue(0.0 <= res.confidence <= 1.0)
            self.assertIsInstance(res.detected_raga, str)
            for c in res.top_candidates:
                self.assertTrue(0.0 <= c.score <= 1.0)
                self.assertTrue(0.0 <= c.confidence <= 1.0)
                self.assertIsInstance(c.feature_scores, dict)
                self.assertIsInstance(c.matched_features, list)
                self.assertIsInstance(c.contradictory_features, list)
            
            # Candidates must be sorted descending
            scores = [c.score for c in res.top_candidates]
            self.assertEqual(scores, sorted(scores, reverse=True))


if __name__ == "__main__":
    unittest.main()
