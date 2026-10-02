"""
Unit tests for the Tala Knowledge Base and TalaDefinition model.

Tests:
1. Existence and completeness of the 6 canonical Hindustani talas.
2. Accurate matra counts, vibhag structures, sam, khali, and tali positions.
3. Strict enforcement of Rupak starting with Khali on beat 1.
4. Correct canonical theka syllable lengths and contents.
5. Invariant validation failure tests for all malformed inputs.
6. Safe, normalized, case-insensitive, and alias lookup APIs.
7. Matra-based filtering.
8. Model immutability (frozen dataclass/Pydantic model).
"""

from typing import Any, Dict, List
import unittest
from pydantic import ValidationError

from backend.app.analysis.tala_knowledge_base import (
    TalaDefinition,
    TALA_KNOWLEDGE_BASE,
    get_tala,
    get_all_talas,
    get_talas_by_matras,
    has_tala,
    normalize_tala_lookup_key,
)


class TestTalaKnowledgeBase(unittest.TestCase):
    """Test suite for Tala Knowledge Base and TalaDefinition."""

    def test_all_six_talas_exist(self):
        """Verify that all six canonical Hindustani talas are defined."""
        expected_ids = {"teental", "dadra", "keharwa", "rupak", "jhaptaal", "ektaal"}
        all_talas = get_all_talas()
        tala_ids = {t.tala_id for t in all_talas}
        self.assertEqual(expected_ids, tala_ids)
        self.assertEqual(len(all_talas), 6)

    def test_canonical_matra_counts(self):
        """Verify accurate beat (matra) counts for each tala."""
        matra_expectations = {
            "teental": 16,
            "dadra": 6,
            "keharwa": 8,
            "rupak": 7,
            "jhaptaal": 10,
            "ektaal": 12,
        }
        for tala_id, expected_matras in matra_expectations.items():
            tala = get_tala(tala_id)
            self.assertIsNotNone(tala, f"Tala '{tala_id}' should exist")
            self.assertEqual(tala.matras, expected_matras)

    def test_canonical_vibhag_structures(self):
        """Verify accurate vibhag divisions for each tala."""
        vibhag_expectations = {
            "teental": [4, 4, 4, 4],
            "dadra": [3, 3],
            "keharwa": [4, 4],
            "rupak": [3, 2, 2],
            "jhaptaal": [2, 3, 2, 3],
            "ektaal": [2, 2, 2, 2, 2, 2],
        }
        for tala_id, expected_vibhags in vibhag_expectations.items():
            tala = get_tala(tala_id)
            self.assertIsNotNone(tala)
            self.assertEqual(tala.vibhag_structure, expected_vibhags)
            self.assertEqual(sum(tala.vibhag_structure), tala.matras)

    def test_canonical_structural_positions(self):
        """Verify Sam, Khali, and Tali structural positions for all 6 talas."""
        structural_expectations = {
            "teental": {
                "sam": 1,
                "khali": [9],
                "tali": [1, 5, 13],
            },
            "dadra": {
                "sam": 1,
                "khali": [4],
                "tali": [1],
            },
            "keharwa": {
                "sam": 1,
                "khali": [5],
                "tali": [1],
            },
            "rupak": {
                "sam": 1,
                "khali": [1],  # Rupak begins on Khali
                "tali": [4, 6],
            },
            "jhaptaal": {
                "sam": 1,
                "khali": [6],
                "tali": [1, 3, 8],
            },
            "ektaal": {
                "sam": 1,
                "khali": [3, 7],
                "tali": [1, 5, 9, 11],
            },
        }
        for tala_id, expected in structural_expectations.items():
            tala = get_tala(tala_id)
            self.assertIsNotNone(tala)
            self.assertEqual(tala.sam_position, expected["sam"])
            self.assertEqual(tala.khali_positions, expected["khali"])
            self.assertEqual(tala.tali_positions, expected["tali"])

    def test_rupak_begins_on_khali(self):
        """Specific check for the key Hindustani convention that Rupak begins with Khali."""
        rupak = get_tala("Rupak")
        self.assertIsNotNone(rupak)
        self.assertEqual(rupak.sam_position, 1)
        self.assertIn(1, rupak.khali_positions)
        self.assertNotIn(1, rupak.tali_positions)
        self.assertEqual(rupak.tali_positions, [4, 6])

    def test_theka_syllable_invariants(self):
        """Verify all canonical talas have theka lengths equal to matras and non-empty bols."""
        for tala in get_all_talas():
            self.assertEqual(len(tala.theka_syllables), tala.matras)
            for i, bol in enumerate(tala.theka_syllables):
                self.assertIsInstance(bol, str)
                self.assertTrue(len(bol.strip()) > 0, f"Bol at beat {i+1} in {tala.name} is empty")

    def test_teental_canonical_theka(self):
        """Verify Teental's canonical 16-bol theka sequence."""
        teental = get_tala("Teental")
        self.assertIsNotNone(teental)
        expected_theka = [
            "Dha", "Dhin", "Dhin", "Dha",
            "Dha", "Dhin", "Dhin", "Dha",
            "Dha", "Tin", "Tin", "Ta",
            "Ta", "Dhin", "Dhin", "Dha",
        ]
        self.assertEqual(teental.theka_syllables, expected_theka)

    def test_case_insensitive_and_alias_lookup(self):
        """Verify resilient lookup across cases, diacritics, and aliases."""
        queries = [
            ("teental", "Teental"),
            ("Teental", "Teental"),
            ("TEENTAL", "Teental"),
            ("Tīntāl", "Teental"),
            ("teentaal", "Teental"),
            ("Tintal", "Teental"),
            ("trital", "Teental"),
            ("dadra", "Dadra"),
            ("Dadra Taal", "Dadra"),
            ("keharwa", "Keharwa"),
            ("Keherwa", "Keharwa"),
            ("kaharwa", "Keharwa"),
            ("rupak", "Rupak"),
            ("Roopak", "Rupak"),
            ("RUPAK TAAL", "Rupak"),
            ("jhaptaal", "Jhaptaal"),
            ("jhaptal", "Jhaptaal"),
            ("Taal Ektaal", "Ektaal"),
            ("Ēktāl", "Ektaal"),
            ("ektal", "Ektaal"),
        ]
        for query, expected_name in queries:
            tala = get_tala(query)
            self.assertIsNotNone(tala, f"Query '{query}' should resolve to {expected_name}")
            self.assertEqual(tala.name, expected_name)
            self.assertTrue(has_tala(query))

    def test_unknown_tala_lookup(self):
        """Verify unknown or malformed lookups safely return None / False."""
        invalid_queries = ["", "   ", "NonExistentTala", "BeethovenSymphony", None, 123]
        for q in invalid_queries:
            self.assertIsNone(get_tala(q))  # type: ignore
            self.assertFalse(has_tala(q))  # type: ignore

    def test_get_talas_by_matras(self):
        """Verify filtering talas by matra count."""
        self.assertEqual([t.name for t in get_talas_by_matras(16)], ["Teental"])
        self.assertEqual([t.name for t in get_talas_by_matras(6)], ["Dadra"])
        self.assertEqual([t.name for t in get_talas_by_matras(8)], ["Keharwa"])
        self.assertEqual([t.name for t in get_talas_by_matras(7)], ["Rupak"])
        self.assertEqual([t.name for t in get_talas_by_matras(10)], ["Jhaptaal"])
        self.assertEqual([t.name for t in get_talas_by_matras(12)], ["Ektaal"])
        self.assertEqual(get_talas_by_matras(5), [])
        self.assertEqual(get_talas_by_matras(-1), [])

    def test_model_immutability(self):
        """Verify TalaDefinition instances cannot be modified in-place."""
        teental = get_tala("Teental")
        self.assertIsNotNone(teental)
        with self.assertRaises((ValidationError, TypeError)):
            teental.matras = 32  # type: ignore

    def test_validation_failure_empty_name(self):
        """Model validation must reject empty or whitespace-only name."""
        with self.assertRaises(ValidationError):
            TalaDefinition(
                name="  ",
                tala_id="custom",
                matras=4,
                vibhag_structure=[2, 2],
                theka_syllables=["Dha", "Ge", "Na", "Ti"],
            )

    def test_validation_failure_invalid_matras(self):
        """Model validation must reject zero or negative matras."""
        with self.assertRaises(ValidationError):
            TalaDefinition(
                name="ZeroTala",
                tala_id="zero",
                matras=0,
                vibhag_structure=[],
                theka_syllables=[],
            )

    def test_validation_failure_mismatched_vibhags(self):
        """Model validation must reject sum(vibhags) != matras."""
        with self.assertRaises(ValidationError):
            TalaDefinition(
                name="BadVibhag",
                tala_id="bad_vibhag",
                matras=16,
                vibhag_structure=[4, 4, 4],  # sums to 12
                theka_syllables=["Dha"] * 16,
            )

    def test_validation_failure_mismatched_theka_length(self):
        """Model validation must reject theka length != matras."""
        with self.assertRaises(ValidationError):
            TalaDefinition(
                name="BadTheka",
                tala_id="bad_theka",
                matras=8,
                vibhag_structure=[4, 4],
                theka_syllables=["Dha", "Dhin", "Na"],  # only 3 bols
            )

    def test_validation_failure_empty_theka_bol(self):
        """Model validation must reject empty theka syllables."""
        with self.assertRaises(ValidationError):
            TalaDefinition(
                name="EmptyBol",
                tala_id="empty_bol",
                matras=4,
                vibhag_structure=[2, 2],
                theka_syllables=["Dha", "  ", "Na", "Ti"],
            )

    def test_validation_failure_sam_out_of_range(self):
        """Model validation must reject sam_position out of 1..matras."""
        with self.assertRaises(ValidationError):
            TalaDefinition(
                name="BadSam",
                tala_id="bad_sam",
                matras=8,
                vibhag_structure=[4, 4],
                sam_position=9,  # out of range
                theka_syllables=["Dha"] * 8,
            )

    def test_validation_failure_khali_out_of_range(self):
        """Model validation must reject khali_positions out of 1..matras."""
        with self.assertRaises(ValidationError):
            TalaDefinition(
                name="BadKhali",
                tala_id="bad_khali",
                matras=8,
                vibhag_structure=[4, 4],
                khali_positions=[0],  # out of range (1-indexed)
                theka_syllables=["Dha"] * 8,
            )

    def test_validation_failure_duplicate_positions(self):
        """Model validation must reject duplicate positions in tali or khali."""
        with self.assertRaises(ValidationError):
            TalaDefinition(
                name="DupTali",
                tala_id="dup_tali",
                matras=8,
                vibhag_structure=[4, 4],
                tali_positions=[1, 1],
                theka_syllables=["Dha"] * 8,
            )

    def test_validation_failure_overlapping_tali_khali(self):
        """Model validation must reject overlapping tali and khali positions."""
        with self.assertRaises(ValidationError):
            TalaDefinition(
                name="Overlap",
                tala_id="overlap",
                matras=8,
                vibhag_structure=[4, 4],
                tali_positions=[1, 5],
                khali_positions=[5],  # Beat 5 cannot be both Tali and Khali
                theka_syllables=["Dha"] * 8,
            )


if __name__ == "__main__":
    unittest.main()
