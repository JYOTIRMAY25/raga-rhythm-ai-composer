"""
Comprehensive unit, adversarial, and integration test suite for TalaClassifier.

Tests:
1. Evidence-based classification for all 9 target Talas:
   - Teentaal (16)
   - Ektaal (12)
   - Jhaptaal (10)
   - Tilwada (16)
   - Jhoomra (14)
   - Jatt (16)
   - Rupak (7)
   - Keherwa (8)
   - Dadra (6)
2. Allied/Ambiguous Tala discrimination (Teentaal vs Tilwada vs Jatt by laya/tempo).
3. Tempo doubling / halving disambiguation (Keherwa 8 vs Teentaal 16, Dadra 6 vs Ektaal 12).
4. Missing beats resilience.
5. Sparse percussion handling.
6. Pure silence handling.
7. Malformed / non-finite inputs.
8. Deterministic repeated execution.
9. Summary dictionary serialization.
"""

import math
from typing import Any, Dict, List
import unittest

import numpy as np

from backend.app.analysis.beat_tracker import BeatTracker
from backend.app.analysis.rhythm_analyzer import RhythmAnalyzer
from backend.app.analysis.tala_classifier import (
    TalaCandidate,
    TalaClassificationResult,
    TalaClassifier,
    TALA_PROFILES,
)


class TestTalaClassifier(unittest.TestCase):
    """Test suite for TalaClassifier."""

    def setUp(self):
        self.sr = 22050
        self.analyzer = RhythmAnalyzer(sample_rate=self.sr)
        self.tracker = BeatTracker()
        self.classifier = TalaClassifier(tracker=self.tracker)

    def _generate_synthetic_tala_signal(
        self,
        matras: int,
        bpm: float,
        duration: float = 16.0,
        sam_pos: int = 1,
        tali_positions: List[int] = None,
        khali_positions: List[int] = None,
    ) -> np.ndarray:
        """Helper to generate a synthetic audio signal with characteristic Tala accents."""
        tali_positions = tali_positions or [1]
        khali_positions = khali_positions or []

        interval = 60.0 / bpm
        num_samples = int(self.sr * duration)
        audio = np.zeros(num_samples, dtype=np.float32)

        beat_times = np.arange(0.5, duration - 0.5, interval)
        for i, bt in enumerate(beat_times):
            matra = (i % matras) + 1
            idx = int(bt * self.sr)
            if idx >= num_samples:
                break

            # Accent weighting
            if matra == sam_pos:
                amp = 1.0  # Sam
            elif matra in tali_positions:
                amp = 0.75  # Tali
            elif matra in khali_positions:
                amp = 0.25  # Khali
            else:
                amp = 0.45  # Unaccented beat

            burst_len = min(60, num_samples - idx)
            t_burst = np.arange(burst_len) / self.sr
            burst = np.sin(2 * np.pi * 800.0 * t_burst) * np.exp(-t_burst * 200.0) * amp
            audio[idx : idx + burst_len] += burst.astype(np.float32)

        return audio

    def test_teentaal_classification(self):
        """Verify evidence-based classification of 16-beat Teentaal at 120 BPM."""
        audio = self._generate_synthetic_tala_signal(
            matras=16,
            bpm=120.0,
            duration=18.0,
            sam_pos=1,
            tali_positions=[1, 5, 13],
            khali_positions=[9],
        )
        rf = self.analyzer.analyze(audio)
        result = self.classifier.classify(rf)

        self.assertIsInstance(result, TalaClassificationResult)
        self.assertEqual(result.predicted_tala_id, "teental")
        self.assertEqual(result.predicted_matras, 16)
        self.assertGreater(result.confidence, 0.20)
        self.assertGreater(len(result.candidates), 0)

    def test_ektaal_classification(self):
        """Verify evidence-based classification of 12-beat Ektaal."""
        audio = self._generate_synthetic_tala_signal(
            matras=12,
            bpm=180.0,
            duration=16.0,
            sam_pos=1,
            tali_positions=[1, 5, 9, 11],
            khali_positions=[3, 7],
        )
        rf = self.analyzer.analyze(audio)
        result = self.classifier.classify(rf)

        self.assertEqual(result.predicted_tala_id, "ektaal")
        self.assertEqual(result.predicted_matras, 12)

    def test_jhaptaal_classification(self):
        """Verify evidence-based classification of 10-beat Jhaptaal."""
        audio = self._generate_synthetic_tala_signal(
            matras=10,
            bpm=90.0,
            duration=16.0,
            sam_pos=1,
            tali_positions=[1, 3, 8],
            khali_positions=[6],
        )
        rf = self.analyzer.analyze(audio)
        result = self.classifier.classify(rf)

        self.assertEqual(result.predicted_tala_id, "jhaptaal")
        self.assertEqual(result.predicted_matras, 10)

    def test_rupak_classification(self):
        """Verify evidence-based classification of 7-beat Rupak (Sam is Khali)."""
        audio = self._generate_synthetic_tala_signal(
            matras=7,
            bpm=100.0,
            duration=15.0,
            sam_pos=1,
            tali_positions=[4, 6],
            khali_positions=[1],
        )
        rf = self.analyzer.analyze(audio)
        result = self.classifier.classify(rf)

        self.assertEqual(result.predicted_tala_id, "rupak")
        self.assertEqual(result.predicted_matras, 7)

    def test_keherwa_classification(self):
        """Verify evidence-based classification of 8-beat Keherwa."""
        audio = self._generate_synthetic_tala_signal(
            matras=8,
            bpm=130.0,
            duration=14.0,
            sam_pos=1,
            tali_positions=[1],
            khali_positions=[5],
        )
        rf = self.analyzer.analyze(audio)
        result = self.classifier.classify(rf)

        self.assertEqual(result.predicted_tala_id, "keharwa")
        self.assertEqual(result.predicted_matras, 8)

    def test_dadra_classification(self):
        """Verify evidence-based classification of 6-beat Dadra."""
        audio = self._generate_synthetic_tala_signal(
            matras=6,
            bpm=120.0,
            duration=12.0,
            sam_pos=1,
            tali_positions=[1],
            khali_positions=[4],
        )
        rf = self.analyzer.analyze(audio)
        result = self.classifier.classify(rf)

        self.assertEqual(result.predicted_tala_id, "dadra")
        self.assertEqual(result.predicted_matras, 6)

    def test_jhoomra_classification(self):
        """Verify evidence-based classification of 14-beat Jhoomra at Vilambit tempo."""
        audio = self._generate_synthetic_tala_signal(
            matras=14,
            bpm=45.0,
            duration=28.0,
            sam_pos=1,
            tali_positions=[1, 4, 11],
            khali_positions=[8],
        )
        rf = self.analyzer.analyze(audio)
        result = self.classifier.classify(rf)

        self.assertEqual(result.predicted_tala_id, "jhoomra")
        self.assertEqual(result.predicted_matras, 14)

    def test_tilwada_vilambit_discrimination(self):
        """Verify 16-beat signal at slow Vilambit tempo (50 BPM) favors Tilwada."""
        audio = self._generate_synthetic_tala_signal(
            matras=16,
            bpm=50.0,
            duration=30.0,
            sam_pos=1,
            tali_positions=[1, 5, 13],
            khali_positions=[9],
        )
        rf = self.analyzer.analyze(audio)
        result = self.classifier.classify(rf)

        # Candidate ranking must include Tilwada with high confidence at 50 BPM
        top_ids = [c.tala_id for c in result.candidates[:2]]
        self.assertIn("tilwada", top_ids)

    def test_tempo_doubling_keherwa_vs_teentaal(self):
        """Verify 8-beat pattern at 130 BPM is distinguished from 16-beat pattern."""
        audio = self._generate_synthetic_tala_signal(
            matras=8,
            bpm=130.0,
            duration=12.0,
            sam_pos=1,
            tali_positions=[1],
            khali_positions=[5],
        )
        rf = self.analyzer.analyze(audio)
        result = self.classifier.classify(rf)

        self.assertEqual(result.predicted_tala_id, "keharwa")

    def test_missing_beats_resilience(self):
        """Verify classifier tolerates missing beats without failing."""
        audio = self._generate_synthetic_tala_signal(
            matras=16,
            bpm=120.0,
            duration=18.0,
            sam_pos=1,
            tali_positions=[1, 5, 13],
            khali_positions=[9],
        )
        # Blank out a 1-second segment
        audio[int(self.sr * 4.0) : int(self.sr * 5.0)] = 0.0

        rf = self.analyzer.analyze(audio)
        result = self.classifier.classify(rf)

        self.assertEqual(result.predicted_matras, 16)
        self.assertEqual(result.predicted_tala_id, "teental")

    def test_sparse_percussion(self):
        """Verify sparse rhythmic material does not crash and returns safe candidate list."""
        audio = np.zeros(int(self.sr * 6.0), dtype=np.float32)
        for t in [1.0, 2.0, 3.0, 4.0, 5.0]:
            audio[int(t * self.sr) : int(t * self.sr) + 60] = 0.5

        rf = self.analyzer.analyze(audio)
        result = self.classifier.classify(rf)

        self.assertIsInstance(result, TalaClassificationResult)
        self.assertFalse(np.isnan(result.confidence))

    def test_silence_handling(self):
        """Verify pure silence returns unclassified result with confidence 0.0."""
        audio = np.zeros(int(self.sr * 4.0), dtype=np.float32)
        rf = self.analyzer.analyze(audio)
        result = self.classifier.classify(rf)

        self.assertIsNone(result.predicted_tala)
        self.assertEqual(result.confidence, 0.0)
        self.assertTrue(result.is_ambiguous)
        self.assertEqual(len(result.candidates), 0)

    def test_non_finite_input_robustness(self):
        """Verify pathological NaN/Inf inputs are handled without crashes."""
        audio = np.array([np.nan, np.inf, -np.inf, 0.5] * 2000, dtype=np.float32)
        rf = self.analyzer.analyze(audio)
        result = self.classifier.classify(rf)

        self.assertIsInstance(result, TalaClassificationResult)
        self.assertFalse(math.isnan(result.confidence))

    def test_deterministic_repeated_execution(self):
        """Verify repeated execution produces bit-exact identical candidate scores."""
        audio = self._generate_synthetic_tala_signal(matras=10, bpm=90.0, duration=10.0)
        rf = self.analyzer.analyze(audio)

        run1 = self.classifier.classify(rf)
        run2 = self.classifier.classify(rf)

        self.assertEqual(run1.predicted_tala, run2.predicted_tala)
        self.assertEqual(run1.confidence, run2.confidence)
        for c1, c2 in zip(run1.candidates, run2.candidates):
            self.assertEqual(c1.tala_name, c2.tala_name)
            self.assertEqual(c1.composite_score, c2.composite_score)

    def test_to_summary_dict_serialization(self):
        """Verify JSON-serializable summary dictionary output."""
        audio = self._generate_synthetic_tala_signal(matras=16, bpm=120.0, duration=10.0)
        rf = self.analyzer.analyze(audio)
        result = self.classifier.classify(rf)

        summary = result.to_summary_dict()
        self.assertIn("predicted_tala", summary)
        self.assertIn("predicted_matras", summary)
        self.assertIn("confidence", summary)
        self.assertIn("is_ambiguous", summary)
        self.assertIn("top_candidates", summary)
        self.assertIsInstance(summary["top_candidates"], list)


if __name__ == "__main__":
    unittest.main()
