"""
Unit and integration tests for Algorithmic Composition Engine, Constraints, and Validator.
"""

import unittest
from backend.app.composition import (
    CompositionEngine,
    CompositionRequest,
    CompositionValidator,
    MelodyGenerator,
    RagaConstraints,
    RhythmGenerator,
    TalaConstraints,
)


class TestCompositionEngine(unittest.TestCase):
    """Test suite for Raga/Tala constraints, deterministic composition generation, and validation."""

    def setUp(self):
        self.engine = CompositionEngine()

    def test_deterministic_seed_reproducibility(self):
        """Invariant: Same seed, raga, tala, bpm produces identical symbolic composition."""
        req1 = CompositionRequest(
            raga_id="yaman",
            tala_id="teental",
            tonic="C#",
            tempo_bpm=84,
            duration_seconds=60,
            seed=424242,
        )
        req2 = CompositionRequest(
            raga_id="yaman",
            tala_id="teental",
            tonic="C#",
            tempo_bpm=84,
            duration_seconds=60,
            seed=424242,
        )

        comp1 = self.engine.compose(req1)
        comp2 = self.engine.compose(req2)

        self.assertEqual(len(comp1.events), len(comp2.events))
        for ev1, ev2 in zip(comp1.events, comp2.events):
            self.assertEqual(ev1.swara, ev2.swara)
            self.assertEqual(ev1.matra, ev2.matra)
            self.assertEqual(ev1.pitch_hz, ev2.pitch_hz)
            self.assertEqual(ev1.duration_matras, ev2.duration_matras)

    def test_different_seeds_produce_variation(self):
        """Different seeds produce distinct melodic phrases while preserving raga constraints."""
        req1 = CompositionRequest(raga_id="bhairav", tala_id="teental", seed=101)
        req2 = CompositionRequest(raga_id="bhairav", tala_id="teental", seed=999)

        comp1 = self.engine.compose(req1)
        comp2 = self.engine.compose(req2)

        swaras1 = [e.swara for e in comp1.events]
        swaras2 = [e.swara for e in comp2.events]
        self.assertNotEqual(swaras1, swaras2)

    def test_raga_constraints_prevent_forbidden_swaras(self):
        """Yaman forbids Shuddha Ma (m), Komal Re (r), Komal Ga (g), Komal Dha (d), Komal Ni (n)."""
        raga_const = RagaConstraints(raga_id="yaman")
        self.assertIn("m", raga_const.forbidden_swaras)
        self.assertIn("r", raga_const.forbidden_swaras)
        self.assertIn("g", raga_const.forbidden_swaras)
        self.assertIn("d", raga_const.forbidden_swaras)
        self.assertIn("n", raga_const.forbidden_swaras)

        req = CompositionRequest(raga_id="yaman", tala_id="teental", seed=555)
        comp = self.engine.compose(req)

        self.assertTrue(comp.validation.valid)
        self.assertEqual(comp.validation.swara_compliance_score, 1.0)
        for ev in comp.events:
            clean_s = ev.swara.replace(".", "").replace("'", "")
            self.assertNotIn(clean_s, raga_const.forbidden_swaras)

    def test_tala_constraints_metric_alignment(self):
        """E.g. Jhaptaal (10 beats) creates cycles with exactly 10 matras."""
        req = CompositionRequest(
            raga_id="bhairavi",
            tala_id="jhaptaal",
            tempo_bpm=90,
            duration_seconds=45,
            seed=777,
        )
        comp = self.engine.compose(req)

        self.assertEqual(comp.matras, 10)
        self.assertEqual(comp.vibhag_structure, "2+3+2+3")
        self.assertTrue(comp.validation.valid)

        for cycle in comp.cycles:
            cycle_duration = sum(ev.duration_matras for ev in cycle.events)
            self.assertAlmostEqual(cycle_duration, 10.0, places=2)

    def test_sam_resolution_on_cadence(self):
        """Every generated composition validates Sam resolution."""
        req = CompositionRequest(
            raga_id="khamaj",
            tala_id="teental",
            duration_seconds=30,
            seed=888,
        )
        comp = self.engine.compose(req)
        self.assertTrue(comp.validation.sam_resolution_passed)

    def test_validator_catches_injected_forbidden_swaras(self):
        """Validator flags error when forbidden swara is explicitly injected."""
        raga_const = RagaConstraints(raga_id="yaman")
        tala_const = TalaConstraints(tala_id="teental")
        validator = CompositionValidator(raga_const, tala_const)

        req = CompositionRequest(raga_id="yaman", tala_id="teental", seed=12)
        comp = self.engine.compose(req)

        # Corrupt one event with forbidden swara 'm' (Shuddha Ma)
        corrupted_cycles = comp.cycles
        corrupted_cycles[0].events[0].swara = "m"

        val_result = validator.validate(corrupted_cycles)
        self.assertFalse(val_result.valid)
        self.assertTrue(any(d.rule == "varjit_swara_violation" for d in val_result.diagnostics))

    def test_all_six_canonical_talas_supported(self):
        """Supports teental, dadra, keharwa, rupak, jhaptaal, ektaal without crashing."""
        canonical_talas = ["teental", "dadra", "keharwa", "rupak", "jhaptaal", "ektaal"]
        for tala_id in canonical_talas:
            req = CompositionRequest(raga_id="yaman", tala_id=tala_id, duration_seconds=20)
            comp = self.engine.compose(req)
            self.assertEqual(comp.tala_id, tala_id)
            self.assertTrue(comp.validation.valid)


if __name__ == "__main__":
    unittest.main()
