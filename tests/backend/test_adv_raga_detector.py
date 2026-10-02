"""
Adversarial and Comprehensive Verification Test Suite for Raga Detection and Motif Matching.

Designed strictly from specification to rigorously test:
1. Knowledge Base expansion (>=60 Hindustani ragas, valid theoretical structures, non-empty pakads)
2. Melodic phrase/pakad parsing (.mphrases-manual.txt formatting, tokenization, lower case 's' normalization, edge cases)
3. Saraga taxonomy aliases and compound raga name resolution
4. Melodic motif matching against SwaraAnalyzer performance output (exact, collapsed, sliding window fuzzy)
5. Unrelated motif isolation (unrelated motifs strictly produce low similarity <= 0.20)
6. Adversarial boundaries: 0 swaras, single swaras, repeated swaras, huge random swara streams
7. Property and fuzz testing: mathematical invariants [0.0, 1.0], ranking monotonicity, idempotence
"""

import math
import random
import string
import unittest
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.app.analysis.motif_matcher import (
    MelodicMotifMatcher,
    MelodicPhraseParser,
    MotifMatchEvidence,
    ParsedMelodicMotif,
    ALL_SWARA_SYMBOLS,
    VALID_SWARA_SET,
)
from backend.app.analysis.raga_detector import (
    RagaDetector,
    RagaAnalysisResult,
    RagaCandidate,
    RAGA_KNOWLEDGE_BASE,
)
from backend.app.analysis.swara_analyzer import (
    SwaraAnalysisResult,
    SwaraSegment,
    SWARA_DEFINITIONS,
)
from backend.app.utils.dataset_adapter import (
    normalize_raga_name,
    SaragaDatasetAdapter,
)


class TestAdversarialRagaDetector(unittest.TestCase):
    """Adversarial and rigorous unit tests for RagaDetector and MotifMatcher."""

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
        """Helper to construct synthetic SwaraAnalysisResult."""
        n = 100
        ts = np.arange(n, dtype=np.float32) / 225.0
        freqs = np.full(n, tonic_hz, dtype=np.float32)
        confs = np.full(n, 0.9, dtype=np.float32)

        total = sum(pcd.values())
        norm_pcd = {k: v / total for k, v in pcd.items()} if total > 0 else pcd
        full_pcd = {s["symbol"]: norm_pcd.get(s["symbol"], 0.0) for s in SWARA_DEFINITIONS}

        if symbols is None or len(symbols) == 0:
            symbols = ["NONE"] * n
        if transitions is None:
            transitions = []

        segments: List[SwaraSegment] = []
        if len(symbols) > 0 and symbols[0] != "NONE":
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
    # 1. Knowledge Base Expansion & Integrity Tests (AC1, AC2)
    # ------------------------------------------------------------------------
    def test_knowledge_base_minimum_size(self):
        """AC1: Knowledge Base must contain at least 60 Hindustani ragas."""
        self.assertGreaterEqual(len(RAGA_KNOWLEDGE_BASE), 60)

    def test_knowledge_base_schema_and_theory_integrity(self):
        """AC1: Every raga entry in KB must have valid structured musical theory attributes."""
        required_keys = {"name", "aliases", "thaat", "swaras", "varjit", "vadi", "samvadi", "aroha", "avaroha", "pakad_motifs", "pcd_template"}
        
        for raga_id, meta in RAGA_KNOWLEDGE_BASE.items():
            self.assertIsInstance(raga_id, str)
            self.assertTrue(raga_id.islower() or "_" in raga_id)
            
            # Check all required keys present
            for k in required_keys:
                self.assertIn(k, meta, f"Raga '{raga_id}' missing key '{k}'")

            # Check swaras
            swaras = meta["swaras"]
            self.assertGreaterEqual(len(swaras), 5, f"Raga '{raga_id}' has fewer than 5 swaras (audav minimum)")
            self.assertLessEqual(len(swaras), 12, f"Raga '{raga_id}' has more than 12 swaras")
            for s in swaras:
                self.assertIn(s, VALID_SWARA_SET, f"Invalid swara '{s}' in raga '{raga_id}'")

            # Check varjit (forbidden) swaras do not overlap with scale swaras
            varjit = meta["varjit"]
            overlap = set(swaras).intersection(set(varjit))
            self.assertEqual(len(overlap), 0, f"Raga '{raga_id}' has overlapping scale & varjit swaras: {overlap}")

            # Check vadi & samvadi are in scale swaras
            if meta["vadi"]:
                self.assertIn(meta["vadi"], swaras, f"Vadi '{meta['vadi']}' not in swaras for '{raga_id}'")
            if meta["samvadi"]:
                self.assertIn(meta["samvadi"], swaras, f"Samvadi '{meta['samvadi']}' not in swaras for '{raga_id}'")

            # Check pakad motifs are non-empty and use valid symbols
            pakads = meta["pakad_motifs"]
            self.assertGreaterEqual(len(pakads), 1, f"Raga '{raga_id}' has empty pakad_motifs")
            for p in pakads:
                self.assertGreaterEqual(len(p), 2, f"Pakad '{p}' in '{raga_id}' has length < 2")
                for sym in p:
                    self.assertIn(sym, VALID_SWARA_SET, f"Invalid symbol '{sym}' in pakad of '{raga_id}'")

            # Check PCD template
            pcd_tpl = meta["pcd_template"]
            self.assertGreaterEqual(len(pcd_tpl), 5)
            tpl_sum = sum(pcd_tpl.values())
            self.assertAlmostEqual(tpl_sum, 1.0, places=1, msg=f"PCD template for '{raga_id}' does not sum near 1.0: {tpl_sum}")

    def test_saraga_dataset_raga_coverage(self):
        """AC2: Every normalized raga found in Saraga Hindustani dataset is covered in KB or aliases."""
        saraga_ragas = [
            "yaman", "bhairavi", "bhairav", "todi", "bhoopali", "malkauns", "bageshri", "desh",
            "kafi", "kedar", "hindol_pancham", "jogiya", "komal_rishabh_asavari", "lalit", "jait_kalyan",
            "shree", "bihag", "marwa", "bhimpalasi", "bairagi", "ahir_bhairav", "bhatiyar", "gaud_malhar",
            "multani", "shuddha_kalyan", "megh", "gawti", "bilaskhani_todi", "hameer", "shuddh_sarang",
            "maru_bihag", "dhani", "puriya", "jog", "abhogi", "bibhas", "nat_bhairav", "rageshree",
            "bahar", "khamaj", "kalavati", "saraswati", "chandrakauns", "suha", "sohani", "triveni_gauri",
            "lalit_pancham", "madhukauns", "nat_kamod", "mishra_piloo", "mishra_kalingada", "poorva",
            "lagan_gandhar", "khokar", "dagori_deepki", "khat", "mian_malhar", "ramdasi_malhar",
            "sawani", "gauri", "kirwani", "puriya_dhanashree", "paraj", "basanti_kedar", "asavari",
            "jaunpuri", "shankara", "tilak_kamod", "durga", "jaijaiwanti"
        ]
        
        all_kb_names = set(RAGA_KNOWLEDGE_BASE.keys())
        for r_id, meta in RAGA_KNOWLEDGE_BASE.items():
            for alias in meta.get("aliases", []):
                all_kb_names.add(alias.lower())

        missing = [r for r in saraga_ragas if r not in all_kb_names]
        self.assertEqual(len(missing), 0, f"Saraga dataset ragas missing from KB: {missing}")

    # ------------------------------------------------------------------------
    # 2. Melodic Phrase Parser Tests (AC3)
    # ------------------------------------------------------------------------
    def test_melodic_phrase_parser_standard_motifs(self):
        """AC3: Parses standard contiguous swara motifs from Saraga .mphrases-manual.txt."""
        cases = [
            ("NrS", ["N", "r", "S"]),
            ("rNdP", ["r", "N", "d", "P"]),
            ("PNSr", ["P", "N", "S", "r"]),
            ("gRm", ["g", "R", "m"]),
            ("DNrGrND", ["D", "N", "r", "G", "r", "N", "D"]),
            ("mPgm", ["m", "P", "g", "m"]),
            ("dS", ["d", "S"]),
        ]
        for raw, expected in cases:
            parsed = MelodicPhraseParser.parse_motif(raw)
            self.assertEqual(parsed.swaras, expected, f"Failed on raw phrase: '{raw}'")
            self.assertTrue(parsed.is_valid)
            self.assertEqual(parsed.length, len(expected))

    def test_melodic_phrase_parser_lowercase_s_normalization(self):
        """AC3: Lowercase 's' is safely normalized to canonical 'S' for Shadja."""
        parsed = MelodicPhraseParser.parse_motif("Rns")
        self.assertEqual(parsed.swaras, ["R", "n", "S"])
        self.assertTrue(parsed.is_valid)

        parsed2 = MelodicPhraseParser.parse_motif("s r g m")
        self.assertEqual(parsed2.swaras, ["S", "r", "g", "m"])

    def test_melodic_phrase_parser_whitespace_and_delimiters(self):
        """AC3: Parses space-separated, comma-separated, and hyphenated swara lists."""
        p1 = MelodicPhraseParser.parse_motif("N R G M D N S")
        self.assertEqual(p1.swaras, ["N", "R", "G", "M", "D", "N", "S"])

        p2 = MelodicPhraseParser.parse_motif("G, M, D, P")
        self.assertEqual(p2.swaras, ["G", "M", "D", "P"])

        p3 = MelodicPhraseParser.parse_motif("m-g-S-r-S")
        self.assertEqual(p3.swaras, ["m", "g", "S", "r", "S"])

    def test_melodic_phrase_parser_invalid_and_empty_inputs(self):
        """AC7: Handles empty strings, non-string inputs, and noise gracefully."""
        self.assertEqual(MelodicPhraseParser.parse_motif("").swaras, [])
        self.assertFalse(MelodicPhraseParser.parse_motif("").is_valid)

        self.assertEqual(MelodicPhraseParser.parse_motif("12345!@#$").swaras, [])
        self.assertFalse(MelodicPhraseParser.parse_motif("12345!@#$").is_valid)

        self.assertEqual(MelodicPhraseParser.parse_motif(None).swaras, [])

    def test_melodic_phrase_parser_bounded_cache_invariants(self):
        """Verify MelodicPhraseParser cache is bounded, reuses entries, and evicts safely."""
        MelodicPhraseParser.clear_cache()
        self.assertEqual(len(MelodicPhraseParser._CACHE), 0)

        # 1. Parse and ensure cached
        res1 = MelodicPhraseParser.parse_motif("N R G")
        self.assertEqual(len(MelodicPhraseParser._CACHE), 1)
        res2 = MelodicPhraseParser.parse_motif("N R G")
        self.assertIs(res1, res2)

        # 2. Add items up to MAX_CACHE_SIZE and verify no unbounded growth
        orig_max = MelodicPhraseParser.MAX_CACHE_SIZE
        try:
            MelodicPhraseParser.MAX_CACHE_SIZE = 10
            MelodicPhraseParser.clear_cache()

            for i in range(25):
                # Insert arbitrary synthetic motif sequences
                MelodicPhraseParser.parse_motif(f"S R G M P {i}")

            # Must never exceed MAX_CACHE_SIZE
            self.assertEqual(len(MelodicPhraseParser._CACHE), 10)

            # Check that recent entries exist and old entries were evicted
            self.assertIn("S R G M P 24", MelodicPhraseParser._CACHE)
            self.assertNotIn("S R G M P 0", MelodicPhraseParser._CACHE)
        finally:
            MelodicPhraseParser.MAX_CACHE_SIZE = orig_max
            MelodicPhraseParser.clear_cache()

    # ------------------------------------------------------------------------
    # 3. Melodic Motif Matching Tests (AC4, AC5)
    # ------------------------------------------------------------------------
    def test_exact_and_collapsed_motif_matching(self):
        """AC4: MelodicMotifMatcher identifies exact and collapsed contiguous pakad motifs."""
        # Yaman pakad: N -> R -> G -> M -> D -> N -> S
        candidate_pakads = [["N", "R", "G"], ["M", "D", "N", "S"], ["G", "M", "D", "P"]]
        
        # Observed stream with sustained/repeated notes (e.g. from SwaraAnalyzer segments)
        observed_segments = ["N", "N", "R", "R", "R", "G", "G", "M", "D", "N", "S", "S"]
        evidence = MelodicMotifMatcher.match_raga_motifs(candidate_pakads, observed_segments)

        self.assertGreater(evidence.match_score, 0.85)
        self.assertGreaterEqual(len(evidence.matched_motifs), 2)
        self.assertTrue(any("N R G" in m for m in evidence.matched_motifs))
        self.assertTrue(any("M D N S" in m for m in evidence.matched_motifs))

    def test_unrelated_motifs_produce_low_similarity(self):
        """AC5: Completely unrelated motifs strictly produce low similarity (<= 0.20)."""
        # Bhairavi motifs (r, g, m, d, n)
        bhairavi_pakads = [["m", "g", "S", "r", "S"], ["d", "P", "m", "P"], ["g", "m", "d", "P"]]
        
        # Performance in Bhoopali / Yaman (S, R, G, P, D with no komal notes)
        yaman_stream = ["S", "R", "G", "P", "D", "S", "D", "P", "G", "R", "S"]
        evidence = MelodicMotifMatcher.match_raga_motifs(bhairavi_pakads, yaman_stream)

        self.assertLessEqual(evidence.match_score, 0.20)
        self.assertEqual(len(evidence.matched_motifs), 0)

    def test_sliding_window_fuzzy_subsequence_similarity(self):
        """AC4: Detects slightly varied/ornamented melodic motifs with sliding window."""
        target = ["P", "m", "g", "R", "S"]
        # Stream has an intermediate grace note: P -> M -> m -> g -> R -> S
        stream = ["P", "M", "m", "g", "R", "S"]
        sim, pos, sub = MelodicMotifMatcher._sliding_window_similarity(target, stream)

        self.assertGreaterEqual(sim, 0.80)
        self.assertEqual(pos, 0)

    # ------------------------------------------------------------------------
    # 4. RagaDetector Multi-Feature Scoring Tests (AC6)
    # ------------------------------------------------------------------------
    def test_raga_detector_shree_profile(self):
        """AC6: Canonical Shree profile (komal r, tivra M, komal d, Pancham) detects Shree."""
        pcd = {"S": 0.16, "r": 0.22, "G": 0.10, "M": 0.14, "P": 0.20, "d": 0.12, "N": 0.06}
        seq = ["r", "N", "d", "P", "P", "N", "S", "r", "G", "r", "S"]
        trans = [("r", "N"), ("N", "d"), ("d", "P"), ("P", "N"), ("N", "S"), ("S", "r"), ("r", "G"), ("G", "r"), ("r", "S")]

        swara_res = self._create_mock_swara_result(pcd, symbols=seq, transitions=trans)
        res = self.detector.detect(swara_res, tonic_input=146.8)

        self.assertEqual(res.detected_raga, "Shree")
        self.assertGreater(res.confidence, 0.70)
        self.assertEqual(res.top_candidates[0].thaat, "Purvi")
        self.assertIn("motif_evidence", res.top_candidates[0].feature_scores)

    def test_raga_detector_marwa_profile(self):
        """AC6: Canonical Marwa profile (komal r, shuddha D, tivra M, Pancham strictly varjit) detects Marwa."""
        pcd = {"S": 0.12, "r": 0.20, "G": 0.22, "M": 0.16, "D": 0.20, "N": 0.10}
        seq = ["D", "N", "r", "G", "r", "G", "r", "S", "D", "M", "G", "r"]
        trans = [("D", "N"), ("N", "r"), ("r", "G"), ("G", "r"), ("r", "S"), ("S", "D"), ("D", "M"), ("M", "G"), ("G", "r")]

        swara_res = self._create_mock_swara_result(pcd, symbols=seq, transitions=trans)
        res = self.detector.detect(swara_res, tonic_input=138.0)

        self.assertEqual(res.detected_raga, "Marwa")
        self.assertGreater(res.confidence, 0.70)
        self.assertEqual(res.top_candidates[0].thaat, "Marwa")

    def test_raga_detector_bhimpalasi_profile(self):
        """AC6: Canonical Bhimpalasi profile (komal g, shuddha m, komal n, shuddha D) detects Bhimpalasi."""
        pcd = {"S": 0.16, "R": 0.10, "g": 0.16, "m": 0.22, "P": 0.16, "D": 0.08, "n": 0.12}
        seq = ["n", "S", "g", "m", "m", "P", "g", "m", "P", "m", "g", "R", "S"]
        trans = [("n", "S"), ("S", "g"), ("g", "m"), ("m", "P"), ("P", "g"), ("g", "m"), ("P", "m"), ("m", "g"), ("g", "R"), ("R", "S")]

        swara_res = self._create_mock_swara_result(pcd, symbols=seq, transitions=trans)
        res = self.detector.detect(swara_res, tonic_input=155.0)

        self.assertEqual(res.detected_raga, "Bhimpalasi")
        self.assertGreater(res.confidence, 0.70)
        self.assertEqual(res.top_candidates[0].thaat, "Kafi")

    def test_raga_detector_bairagi_profile(self):
        """AC6: Canonical Bairagi pentatonic profile (S, r, m, P, n) detects Bairagi."""
        pcd = {"S": 0.22, "r": 0.18, "m": 0.22, "P": 0.20, "n": 0.18}
        seq = ["P", "m", "r", "P", "n", "S", "r", "m", "P", "n", "P", "m", "r", "S"]
        trans = [("P", "m"), ("m", "r"), ("r", "P"), ("P", "n"), ("n", "S"), ("S", "r"), ("r", "m"), ("m", "P"), ("P", "n"), ("n", "P"), ("m", "r"), ("r", "S")]

        swara_res = self._create_mock_swara_result(pcd, symbols=seq, transitions=trans)
        res = self.detector.detect(swara_res, tonic_input=140.0)

        self.assertEqual(res.detected_raga, "Bairagi")
        self.assertGreater(res.confidence, 0.70)
        self.assertEqual(res.top_candidates[0].thaat, "Bhairav")

    # ------------------------------------------------------------------------
    # 5. Alias and Compound Name Normalization Tests (AC2)
    # ------------------------------------------------------------------------
    def test_dataset_adapter_raga_name_normalization_extended(self):
        """AC2: Tests normalization for all Saraga compound and transliterated raga names."""
        test_cases = [
            ("Shree", "shree"),
            ("Śrī", "shree"),
            ("Miya Malhar", "mian_malhar"),
            ("Miyan Malhar", "mian_malhar"),
            ("Abhogi", "abhogi"),
            ("Ahir Bhairav", "ahir_bhairav"),
            ("Aahir Bhairon", "ahir_bhairav"),
            ("Nat Bhairon", "nat_bhairav"),
            ("Bhatiyar", "bhatiyar"),
            ("Gaud Malhar", "gaud_malhar"),
            ("Multani", "multani"),
            ("Shuddha Kalyan", "shuddha_kalyan"),
            ("Sudh Kalyan", "shuddha_kalyan"),
            ("Megh", "megh"),
            ("Gawti", "gawti"),
            ("Gavti", "gavti"),
            ("Bilaskhani Todi", "bilaskhani_todi"),
            ("Hameer", "hameer"),
            ("Hamir", "hameer"),
            ("Shuddh Sarang", "shuddha_sarang"),
            ("Sudh Sarang", "shuddha_sarang"),
            ("Maru Bihag", "maru_bihag"),
            ("Marubihag", "maru_bihag"),
            ("Dhani", "dhani"),
            ("Puriya", "puriya"),
            ("Jog", "jog"),
            ("Bibhas", "bibhas"),
            ("Vibhas", "bibhas"),
            ("Rageshree", "rageshree"),
            ("Rageshri", "rageshree"),
            ("Bahar", "bahar"),
            ("Maajh Khamaj", "khamaj"),
            ("Majh Khamaj", "khamaj"),
            ("Kalavati", "kalavati"),
            ("Saraswati", "saraswati"),
            ("Chandrakauns", "chandrakauns"),
            ("Suha", "sooha_kanada"),
            ("Sooha Kanada", "sooha_kanada"),
            ("Sohani", "sohani"),
            ("Sohini", "sohani"),
            ("Triveni Gauri", "triveni"),
            ("Lalit Pancham", "lalit_pancham"),
            ("Madhukauns", "madhukauns"),
            ("Nat Kamod", "nat_kamod"),
            ("Mishra Piloo", "mishra_piloo"),
            ("Piloo", "pilu"),
            ("Mishra Kalingada", "mishra_kalingada"),
            ("Poorva", "poorva"),
            ("Lagan Gandhar", "lagan_gandhar"),
            ("Khokar", "khokar"),
            ("Dagori Deepki", "dagori_deepki"),
            ("Dagori", "dagori_deepki"),
            ("Deepki", "dagori_deepki"),
            ("Khat", "khat_todi"),
            ("Khat Todi", "khat_todi"),
            ("Ramdasi Malhar", "ramdasi_malhar"),
            ("Sawani", "sawani"),
            ("Gauri", "gauri"),
            ("Kirwani", "kirwani"),
            ("Puriya Dhanashree", "puriya_dhanashree"),
            ("Paraj", "paraj"),
            ("Basanti Kedar", "basanti_kedar"),
        ]

        for raw, expected in test_cases:
            norm = normalize_raga_name(raw)
            self.assertEqual(norm, expected, f"Failed normalizing '{raw}', got '{norm}' expected '{expected}'")

    # ------------------------------------------------------------------------
    # 6. Boundary, Error, and NaN/Inf Protection Tests (AC7)
    # ------------------------------------------------------------------------
    def test_adversarial_empty_and_zero_segments(self):
        """AC7: Handles zero segments and empty PCD without crashing."""
        empty_pcd = {s: 0.0 for s in ALL_SWARA_SYMBOLS}
        swara_res = self._create_mock_swara_result(empty_pcd, symbols=[], coverage_pct=0.0)
        res = self.detector.detect(swara_res, tonic_input=140.0)

        self.assertEqual(res.detected_raga, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(res.confidence, 0.0)
        self.assertEqual(len(res.top_candidates), 0)

    def test_adversarial_all_nan_inf_swara_distribution(self):
        """AC7: Non-finite PCD inputs (NaN/Inf) are cleanly sanitized to 0.0."""
        pcd = {"S": float("nan"), "R": float("inf"), "G": float("-inf"), "P": 0.5}
        swara_res = self._create_mock_swara_result(pcd)
        res = self.detector.detect(swara_res, tonic_input=140.0)

        self.assertIsInstance(res.detected_raga, str)
        self.assertTrue(np.isfinite(res.confidence))
        for c in res.top_candidates:
            self.assertTrue(np.isfinite(c.score))
            self.assertTrue(np.isfinite(c.confidence))

    # ------------------------------------------------------------------------
    # 7. Property / Fuzz Testing for Mathematical Invariants (AC8)
    # ------------------------------------------------------------------------
    def test_property_fuzz_mathematical_invariants(self):
        """AC8: Fuzzes 50 randomized PCD and segment streams to ensure strict bounds [0.0, 1.0]."""
        for _ in range(50):
            # Generate random 12-dimensional Dirichlet-like PCD
            weights = np.random.exponential(scale=1.0, size=12)
            weights /= weights.sum()
            rand_pcd = {sym: float(w) for sym, w in zip(ALL_SWARA_SYMBOLS, weights)}

            # Random swara symbol sequence
            rand_symbols = random.choices(ALL_SWARA_SYMBOLS, k=random.randint(10, 100))
            rand_transitions = [(rand_symbols[i], rand_symbols[i + 1]) for i in range(len(rand_symbols) - 1)]
            cov = random.uniform(15.0, 100.0)
            tonic = random.uniform(100.0, 300.0)

            swara_res = self._create_mock_swara_result(
                rand_pcd,
                symbols=rand_symbols,
                transitions=rand_transitions,
                coverage_pct=cov,
                tonic_hz=tonic,
            )
            res = self.detector.detect(swara_res, tonic_input=tonic)

            self.assertIsInstance(res.detected_raga, str)
            self.assertTrue(0.0 <= res.confidence <= 1.0, f"Confidence out of bounds: {res.confidence}")
            self.assertIsInstance(res.top_candidates, list)
            
            # Check candidate scores strictly descending and in [0.0, 1.0]
            prev_score = 1.01
            for c in res.top_candidates:
                self.assertTrue(0.0 <= c.score <= 1.0, f"Candidate score out of bounds: {c.score}")
                self.assertTrue(0.0 <= c.confidence <= 1.0, f"Candidate conf out of bounds: {c.confidence}")
                self.assertLessEqual(c.score, prev_score + 1e-6, "Candidates not sorted descending by score")
                prev_score = c.score


if __name__ == "__main__":
    unittest.main()
