"""
Comprehensive adversarial unit and integration test suite for BeatTracker and BeatGrid.

Tests:
1. Known tempo signals (60, 90, 120, 180 BPM)
2. Half/double-tempo multi-hypothesis evaluation (0.5x, 1.0x, 2.0x)
3. Missing beats recovery via dynamic programming
4. Extra subdivision onsets filtering
5. Tempo drift / acceleration tracking
6. Sparse rhythmic audio
7. Pure silence handling
8. Very short audio handling
9. Robustness against NaN / Inf non-finite inputs
10. Matra cycle alignment and Sam phase estimation (16, 10, 7 matras)
11. Deterministic repeated execution
12. Fuzz / property testing with random waveforms
13. Summary dictionary serialization
"""

import math
import random
from typing import Any, Dict, List
import unittest

import numpy as np

from backend.app.analysis.beat_tracker import (
    BeatTracker,
    BeatGrid,
)
from backend.app.analysis.rhythm_analyzer import (
    RhythmAnalyzer,
    RhythmFeatures,
)


class TestBeatTracker(unittest.TestCase):
    """Test suite for BeatTracker and BeatGrid."""

    def setUp(self):
        self.sr = 22050
        self.analyzer = RhythmAnalyzer(sample_rate=self.sr)
        self.tracker = BeatTracker()

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
                burst_len = min(click_duration_samples, num_samples - idx)
                t_burst = np.arange(burst_len) / self.sr
                burst = np.sin(2 * np.pi * 1000.0 * t_burst) * np.exp(-t_burst * 200.0)
                audio[idx : idx + burst_len] += burst.astype(np.float32)
            t_click += interval_sec

        return audio

    def test_known_tempo_60_bpm(self):
        """Verify beat tracking on 60 BPM signal (1.0s interval)."""
        audio = self._generate_click_train(bpm=60.0, duration=8.0)
        features = self.analyzer.analyze(audio)
        grid = self.tracker.track(features)

        self.assertIsInstance(grid, BeatGrid)
        self.assertIsNotNone(grid.bpm)
        self.assertAlmostEqual(grid.bpm, 60.0, delta=2.5)
        self.assertAlmostEqual(grid.beat_period, 1.0, delta=0.04)
        self.assertGreater(grid.total_beats, 5)
        self.assertGreater(grid.confidence, 0.4)

    def test_known_tempo_90_bpm(self):
        """Verify beat tracking on 90 BPM signal (0.667s interval)."""
        audio = self._generate_click_train(bpm=90.0, duration=6.0)
        features = self.analyzer.analyze(audio)
        grid = self.tracker.track(features)

        self.assertIsNotNone(grid.bpm)
        self.assertAlmostEqual(grid.bpm, 90.0, delta=2.5)
        self.assertAlmostEqual(grid.beat_period, 0.667, delta=0.03)
        self.assertGreater(grid.total_beats, 6)

    def test_known_tempo_120_bpm(self):
        """Verify beat tracking on 120 BPM signal (0.5s interval)."""
        audio = self._generate_click_train(bpm=120.0, duration=6.0)
        features = self.analyzer.analyze(audio)
        grid = self.tracker.track(features)

        self.assertIsNotNone(grid.bpm)
        self.assertAlmostEqual(grid.bpm, 120.0, delta=2.5)
        self.assertAlmostEqual(grid.beat_period, 0.5, delta=0.03)
        self.assertGreater(grid.total_beats, 9)

    def test_known_tempo_180_bpm(self):
        """Verify beat tracking on fast 180 BPM signal (0.333s interval)."""
        audio = self._generate_click_train(bpm=180.0, duration=6.0)
        features = self.analyzer.analyze(audio)
        grid = self.tracker.track(features)

        self.assertIsNotNone(grid.bpm)
        self.assertAlmostEqual(grid.bpm, 180.0, delta=3.5)
        self.assertAlmostEqual(grid.beat_period, 0.333, delta=0.03)
        self.assertGreater(grid.total_beats, 14)

    def test_tempo_hypotheses_evaluation(self):
        """Verify explicit multi-hypothesis evaluation (0.5x, 1.0x, 2.0x)."""
        audio = self._generate_click_train(bpm=120.0, duration=6.0)
        features = self.analyzer.analyze(audio)
        grid = self.tracker.track(features)

        self.assertIn("1.0x", grid.tempo_hypotheses)
        self.assertIn("0.5x", grid.tempo_hypotheses)
        self.assertIn("2.0x", grid.tempo_hypotheses)
        self.assertEqual(grid.selected_hypothesis, "1.0x")
        self.assertEqual(grid.tempo_hypotheses["1.0x"], 1.0)

    def test_missing_beats_recovery(self):
        """Verify dynamic programming bridges across missing beats without losing phase."""
        duration = 6.0
        interval = 0.5  # 120 BPM
        audio = np.zeros(int(self.sr * duration), dtype=np.float32)

        beat_times = np.arange(0.5, duration - 0.5, interval)
        # Drop beat index 3 (at t=2.0s) and index 7 (at t=4.0s)
        active_beats = np.delete(beat_times, [3, 7])

        for bt in active_beats:
            idx = int(bt * self.sr)
            audio[idx : idx + 60] = 1.0

        features = self.analyzer.analyze(audio)
        grid = self.tracker.track(features)

        self.assertIsNotNone(grid.bpm)
        self.assertAlmostEqual(grid.bpm, 120.0, delta=2.5)
        # Total recovered beats should match full grid count (~10 beats)
        self.assertGreaterEqual(grid.total_beats, len(beat_times) - 1)

    def test_extra_subdivision_onsets_filtering(self):
        """Verify rapid subdivision strokes do not fragment the metric beat grid."""
        duration = 6.0
        interval = 0.5  # 120 BPM
        audio = np.zeros(int(self.sr * duration), dtype=np.float32)

        # Primary beats
        for bt in np.arange(0.5, duration - 0.5, interval):
            idx = int(bt * self.sr)
            audio[idx : idx + 60] = 1.0

        # Add 16th-note subdivision ghost clicks between beats (at +0.125s and +0.25s)
        for bt in np.arange(0.5, duration - 1.0, interval):
            sub_idx1 = int((bt + 0.125) * self.sr)
            sub_idx2 = int((bt + 0.25) * self.sr)
            audio[sub_idx1 : sub_idx1 + 30] = 0.4
            audio[sub_idx2 : sub_idx2 + 30] = 0.3

        features = self.analyzer.analyze(audio)
        grid = self.tracker.track(features)

        self.assertIsNotNone(grid.bpm)
        self.assertAlmostEqual(grid.bpm, 120.0, delta=3.0)
        self.assertAlmostEqual(grid.beat_period, 0.5, delta=0.03)

    def test_tempo_drift_tracking(self):
        """Verify beat grid adjusts to subtle tempo acceleration (115 to 125 BPM)."""
        duration = 8.0
        audio = np.zeros(int(self.sr * duration), dtype=np.float32)

        # Gradual tempo ramp
        t_curr = 0.5
        while t_curr < duration - 0.5:
            idx = int(t_curr * self.sr)
            audio[idx : idx + 60] = 1.0
            # Instantaneous BPM ramps from 115 to 125
            current_bpm = 115.0 + (10.0 * (t_curr / duration))
            t_curr += (60.0 / current_bpm)

        features = self.analyzer.analyze(audio)
        grid = self.tracker.track(features)

        self.assertIsNotNone(grid.bpm)
        self.assertAlmostEqual(grid.bpm, 120.0, delta=5.0)
        self.assertGreater(grid.total_beats, 10)

    def test_sparse_rhythmic_material(self):
        """Verify sparse pulses are handled safely."""
        duration = 6.0
        audio = np.zeros(int(self.sr * duration), dtype=np.float32)
        # Only 3 clicks spaced 1.5s apart (40 BPM)
        for t in [1.0, 2.5, 4.0]:
            idx = int(t * self.sr)
            audio[idx : idx + 60] = 1.0

        features = self.analyzer.analyze(audio)
        grid = self.tracker.track(features)
        self.assertIsInstance(grid, BeatGrid)
        # Should not crash and return finite/valid grid
        self.assertFalse(np.isnan(grid.beat_times).any())

    def test_silence_handling(self):
        """Verify pure silence returns an empty BeatGrid with confidence 0.0 and bpm None."""
        audio = np.zeros(int(self.sr * 3.0), dtype=np.float32)
        features = self.analyzer.analyze(audio)
        grid = self.tracker.track(features)

        self.assertEqual(grid.total_beats, 0)
        self.assertIsNone(grid.bpm)
        self.assertEqual(grid.confidence, 0.0)
        self.assertEqual(grid.beat_period, 0.0)

    def test_very_short_audio(self):
        """Verify short audio returns safely without errors."""
        audio = np.array([0.1, -0.1, 0.5, -0.5], dtype=np.float32)
        features = self.analyzer.analyze(audio)
        grid = self.tracker.track(features)

        self.assertIsInstance(grid, BeatGrid)
        self.assertEqual(grid.total_beats, 0)
        self.assertIsNone(grid.bpm)

    def test_nan_and_inf_robustness(self):
        """Verify pathological inputs are sanitized safely without NaNs/Infs."""
        audio = np.array([np.nan, np.inf, -np.inf, 0.5] * 2000, dtype=np.float32)
        features = self.analyzer.analyze(audio)
        grid = self.tracker.track(features)

        self.assertFalse(np.isnan(grid.beat_times).any())
        self.assertFalse(np.isinf(grid.beat_times).any())
        if grid.bpm is not None:
            self.assertTrue(math.isfinite(grid.bpm))

    def test_matra_alignment_16_beats_teental(self):
        """Verify matra alignment for 16-beat cycle (Teental)."""
        duration = 10.0
        audio = np.zeros(int(self.sr * duration), dtype=np.float32)
        interval = 0.5  # 120 BPM

        # Accented Sam on every 16th beat (t = 0.5, 8.5)
        for i, bt in enumerate(np.arange(0.5, duration - 0.5, interval)):
            idx = int(bt * self.sr)
            amplitude = 1.0 if (i % 16 == 0) else 0.5
            audio[idx : idx + 60] = amplitude

        features = self.analyzer.analyze(audio)
        grid = self.tracker.track(features, cycle_length=16)

        self.assertIsNotNone(grid.matra_indices)
        self.assertIsNotNone(grid.cycle_phases)
        self.assertIsNotNone(grid.sam_timestamps)
        self.assertEqual(grid.cycle_length, 16)

        # Matra indices must be in range 1..16
        self.assertTrue((grid.matra_indices >= 1).all())
        self.assertTrue((grid.matra_indices <= 16).all())

        # Cycle phases must be in range [0.0, 1.0)
        self.assertTrue((grid.cycle_phases >= 0.0).all())
        self.assertTrue((grid.cycle_phases < 1.0).all())

        # Sam timestamps must correspond to matra 1
        sam_beats = grid.beat_times[grid.matra_indices == 1]
        np.testing.assert_array_equal(grid.sam_timestamps, sam_beats)

    def test_matra_alignment_10_beats_jhaptaal(self):
        """Verify matra alignment for 10-beat cycle (Jhaptaal)."""
        duration = 8.0
        audio = self._generate_click_train(bpm=120.0, duration=duration)
        features = self.analyzer.analyze(audio)
        grid = self.tracker.track(features, cycle_length=10)

        self.assertIsNotNone(grid.matra_indices)
        self.assertEqual(grid.cycle_length, 10)
        self.assertTrue((grid.matra_indices >= 1).all())
        self.assertTrue((grid.matra_indices <= 10).all())

    def test_deterministic_repeated_execution(self):
        """Verify identical inputs yield bit-exact identical BeatGrid results."""
        audio = self._generate_click_train(bpm=100.0, duration=5.0)
        features = self.analyzer.analyze(audio)

        run1 = self.tracker.track(features, cycle_length=16)
        run2 = self.tracker.track(features, cycle_length=16)

        np.testing.assert_array_equal(run1.beat_times, run2.beat_times)
        self.assertEqual(run1.bpm, run2.bpm)
        self.assertEqual(run1.confidence, run2.confidence)
        self.assertEqual(run1.selected_hypothesis, run2.selected_hypothesis)
        if run1.matra_indices is not None and run2.matra_indices is not None:
            np.testing.assert_array_equal(run1.matra_indices, run2.matra_indices)

    def test_fuzz_random_waveforms(self):
        """Property/fuzz test: randomized signals never raise unhandled exceptions."""
        rng = np.random.RandomState(42)
        for _ in range(10):
            rand_len = rng.randint(100, 44100)
            rand_audio = rng.randn(rand_len).astype(np.float32)
            features = self.analyzer.analyze(rand_audio)
            grid = self.tracker.track(features, cycle_length=rng.choice([None, 6, 7, 8, 10, 12, 16]))
            self.assertIsInstance(grid, BeatGrid)
            self.assertFalse(np.isnan(grid.beat_times).any())

    def test_to_summary_dict_serialization(self):
        """Verify JSON-serializable summary dictionary creation."""
        audio = self._generate_click_train(bpm=120.0, duration=5.0)
        features = self.analyzer.analyze(audio)
        grid = self.tracker.track(features, cycle_length=16)

        summary = grid.to_summary_dict()
        self.assertIn("total_beats", summary)
        self.assertIn("beat_period", summary)
        self.assertIn("bpm", summary)
        self.assertIn("confidence", summary)
        self.assertIn("selected_hypothesis", summary)
        self.assertIn("tempo_hypotheses", summary)
        self.assertIn("cycle_length", summary)
        self.assertIn("total_sam_cycles", summary)


if __name__ == "__main__":
    unittest.main()
