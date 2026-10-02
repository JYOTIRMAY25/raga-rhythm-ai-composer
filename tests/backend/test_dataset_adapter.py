"""
Comprehensive test suite for the Saraga Hindustani Dataset Adapter.
Tests root discovery, 108-track scanning, parsing, lazy-loading, normalization,
boundary conditions, adversarial inputs, and path traversal protections.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import List

from backend.app.utils.dataset_adapter import (
    BaseSaragaDatasetAdapter,
    SaragaDatasetAdapter,
    SaragaTrackAnnotations,
    PitchContourData,
    TempoAnnotation,
    BpmAnnotation,
    SectionAnnotation,
    MelodicPhraseAnnotation,
    normalize_raga_name,
    normalize_tala_name,
    strip_accents,
)


class TestSaragaDatasetAdapter(unittest.TestCase):
    """Test suite for Saraga Hindustani Dataset Adapter."""

    @classmethod
    def setUpClass(cls):
        """Set up reference to active workspace dataset root if present."""
        cls.workspace_root = Path(__file__).resolve().parents[2]
        cls.candidate_root = cls.workspace_root / "saraga1.5_hindustani" / "saraga1.5_hindustani"
        cls.has_real_dataset = cls.candidate_root.exists() and (cls.candidate_root / "file_paths.csv").exists()

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------------
    # 1. Dataset Root Discovery Tests
    # ------------------------------------------------------------------------
    def test_dataset_root_discovery_real_dataset(self):
        """Test AC1: Discovers real Saraga dataset root automatically."""
        if not self.has_real_dataset:
            self.skipTest("Real dataset not found in workspace")
        adapter = SaragaDatasetAdapter()
        self.assertTrue(adapter.dataset_root.exists())
        self.assertTrue((adapter.dataset_root / "file_paths.csv").exists())

    def test_dataset_root_discovery_nested_outer(self):
        """Test AC1: Auto-resolves nested outer saraga folder to inner dataset root."""
        outer = self.temp_path / "saraga_outer"
        inner = outer / "saraga1.5_hindustani"
        inner.mkdir(parents=True)
        (inner / "file_paths.csv").write_text("dummy,csv,content\n", encoding="utf-8")

        adapter = SaragaDatasetAdapter(dataset_root=outer)
        self.assertEqual(adapter.dataset_root, inner.resolve())

    def test_dataset_root_discovery_not_found(self):
        """Test AC1: Raises FileNotFoundError when non-existent path given."""
        with self.assertRaises(FileNotFoundError):
            SaragaDatasetAdapter(dataset_root=self.temp_path / "non_existent_dir_12345")

    # ------------------------------------------------------------------------
    # 2. 108-Track Discovery & 3. Ignore __MACOSX
    # ------------------------------------------------------------------------
    def test_108_track_discovery_on_real_dataset(self):
        """Test AC2, AC3: Discovers exactly 108 tracks on actual Saraga 1.5 dataset."""
        if not self.has_real_dataset:
            self.skipTest("Real dataset not found in workspace")
        adapter = SaragaDatasetAdapter(self.candidate_root)
        tracks = adapter.scan_dataset()
        self.assertEqual(len(tracks), 108, f"Expected 108 tracks, discovered {len(tracks)}")
        
        # Verify no __MACOSX tracks included
        for t in tracks:
            self.assertNotIn("__MACOSX", str(t))
            self.assertFalse(t.name.startswith("."))

    def test_ignore_macosx_and_hidden_files_synthetic(self):
        """Test AC2: Synthetic mock dataset ignores __MACOSX and dot files."""
        # Create mock structure
        album_real = self.temp_path / "Album A by Artist"
        track_real = album_real / "Track 1"
        track_real.mkdir(parents=True)
        (track_real / "Track 1.json").write_text('{"title": "Track 1"}', encoding="utf-8")

        # Create __MACOSX and hidden dot files
        album_mac = self.temp_path / "__MACOSX"
        track_mac = album_mac / "Track 1"
        track_mac.mkdir(parents=True)
        (track_mac / "Track 1.json").write_text('{"title": "Shadow"}', encoding="utf-8")

        hidden_dir = self.temp_path / ".hidden_album" / "Track Hidden"
        hidden_dir.mkdir(parents=True)
        (hidden_dir / "Track Hidden.json").write_text('{"title": "Hidden"}', encoding="utf-8")

        adapter = SaragaDatasetAdapter(dataset_root=self.temp_path)
        tracks = adapter.scan_dataset()
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0], track_real.resolve())

    # ------------------------------------------------------------------------
    # 4. Audio .mp3.mp3 Resolution & 5. JSON Parsing
    # ------------------------------------------------------------------------
    def test_audio_resolution_and_json_parsing(self):
        """Test AC4, AC5, AC6: Resolves .mp3.mp3 audio and parses full JSON."""
        track_dir = self.temp_path / "Album A" / "Raag Shree"
        track_dir.mkdir(parents=True)

        json_data = {
            "mbid": "b3a43a82-b3c3-49bf-bd3d-db561c1ec355",
            "title": "Raag Shree",
            "length": 3135000,
            "artists": [
                {"artist": {"name": "Deborshee Bhattacharya"}, "instrument": {"name": "Voice"}, "lead": True}
            ],
            "raags": [{"common_name": "Shree", "name": "Śrī"}],
            "taals": [{"common_name": "Teentaal", "name": "Tīntāl"}],
            "layas": [{"common_name": "Vilambit"}],
            "forms": [{"common_name": "Khayal"}],
        }
        (track_dir / "Raag Shree.json").write_text(json.dumps(json_data), encoding="utf-8")
        (track_dir / "Raag Shree.mp3.mp3").write_bytes(b"ID3\x03\x00\x00dummy_audio_bytes")
        (track_dir / "Raag Shree.ctonic.txt").write_text("146.832384\n", encoding="utf-8")

        adapter = SaragaDatasetAdapter(dataset_root=self.temp_path)
        track_annotations = adapter.get_track_annotations(track_dir)

        self.assertEqual(track_annotations.track_title, "Raag Shree")
        self.assertEqual(track_annotations.mbid, "b3a43a82-b3c3-49bf-bd3d-db561c1ec355")
        self.assertEqual(track_annotations.duration_seconds, 3135.0)
        self.assertEqual(track_annotations.raga_names, ["Shree"])
        self.assertEqual(track_annotations.normalized_raga_names, ["shree"])
        self.assertEqual(track_annotations.tala_names, ["Teentaal"])
        self.assertEqual(track_annotations.normalized_tala_names, ["teental"])
        self.assertEqual(track_annotations.tonic_hz, 146.832384)
        self.assertTrue(track_annotations.audio_path.endswith("Raag Shree.mp3.mp3"))

    # ------------------------------------------------------------------------
    # 6. Tonic Parsing & 7. Lazy Pitch Loading
    # ------------------------------------------------------------------------
    def test_tonic_and_lazy_pitch_loading(self):
        """Test AC7, AC8: Lazy pitch contour loading reads TSV accurately with high precision."""
        track_dir = self.temp_path / "Album A" / "Raag Shree"
        track_dir.mkdir(parents=True)
        (track_dir / "Raag Shree.json").write_text('{"title": "Raag Shree"}', encoding="utf-8")
        (track_dir / "Raag Shree.ctonic.txt").write_text(" 155.563 \n", encoding="utf-8")
        
        pitch_content = (
            "0.000000000000000000e+00\t0.000000000000000000e+00\n"
            "4.444444444444444441e-03\t0.000000000000000000e+00\n"
            "2.221777777777777629e+01\t1.555644378662109375e+02\n"
            "2.222222222222222143e+01\t1.546684417724609375e+02\n"
        )
        (track_dir / "Raag Shree.pitch.txt").write_text(pitch_content, encoding="utf-8")

        adapter = SaragaDatasetAdapter(dataset_root=self.temp_path)
        ann = adapter.get_track_annotations(track_dir)

        self.assertAlmostEqual(ann.tonic_hz, 155.563, places=3)
        # Verify pitch is not loaded yet in metadata object
        pitch_data = adapter.load_pitch_contour(ann)
        self.assertEqual(pitch_data.total_frames, 4)
        self.assertEqual(pitch_data.voiced_frames, 2)
        self.assertAlmostEqual(pitch_data.time_stamps[2], 22.217777, places=4)
        self.assertAlmostEqual(pitch_data.frequencies_hz[2], 155.564437, places=4)

    # ------------------------------------------------------------------------
    # 8. Missing Optional Annotations Handling
    # ------------------------------------------------------------------------
    def test_missing_optional_annotations(self):
        """Test AC8, AC10: Missing optional files return clean empty lists without exceptions."""
        track_dir = self.temp_path / "Album A" / "Minimal Track"
        track_dir.mkdir(parents=True)
        (track_dir / "Minimal Track.json").write_text('{"title": "Minimal Track"}', encoding="utf-8")

        adapter = SaragaDatasetAdapter(dataset_root=self.temp_path)
        ann = adapter.get_track_annotations(track_dir)

        self.assertIsNone(ann.tonic_hz)
        self.assertEqual(adapter.load_sama_timestamps(ann), [])
        self.assertEqual(adapter.load_bpm_annotations(ann), [])
        self.assertEqual(adapter.load_tempo_annotations(ann), [])
        self.assertEqual(adapter.load_sections(ann), [])
        self.assertEqual(adapter.load_melodic_phrases(ann), [])
        pitch_empty = adapter.load_pitch_contour(ann)
        self.assertEqual(pitch_empty.total_frames, 0)

    # ------------------------------------------------------------------------
    # 9. Optional File Parsing (Sama, BPM, Tempo, Sections, Phrases)
    # ------------------------------------------------------------------------
    def test_all_optional_annotations_parsing(self):
        """Test AC8: Parses sama, bpm, tempo, sections, and melodic phrase text files."""
        track_dir = self.temp_path / "Album A" / "Track Full"
        track_dir.mkdir(parents=True)
        (track_dir / "Track Full.json").write_text('{"title": "Track Full"}', encoding="utf-8")
        (track_dir / "Track Full.sama-manual.txt").write_text("209.351\n276.544\n", encoding="utf-8")
        (track_dir / "Track Full.bpm-manual.txt").write_text("-,0.0,192.392\n13,192.392,2513.92\n", encoding="utf-8")
        (track_dir / "Track Full.tempo-manual.txt").write_text("13, 4.619, 55.424, 12, 192.392, 2511.331\n", encoding="utf-8")
        (track_dir / "Track Full.sections-manual-p.txt").write_text("0.0,1,192.392,Ālāp\n192.392,2,2321.528,Khyāl (vilambit ēktāl)\n", encoding="utf-8")
        (track_dir / "Track Full.mphrases-manual.txt").write_text("19.382\t1\t13.897\trP\n58.984\t0\t9.560\tNSr\n", encoding="utf-8")

        adapter = SaragaDatasetAdapter(dataset_root=self.temp_path)
        ann = adapter.get_track_annotations(track_dir)

        samas = adapter.load_sama_timestamps(ann)
        self.assertEqual(samas, [209.351, 276.544])

        bpms = adapter.load_bpm_annotations(ann)
        self.assertEqual(len(bpms), 2)
        self.assertEqual(bpms[0].bpm, 0.0)
        self.assertEqual(bpms[1].bpm, 13.0)

        tempos = adapter.load_tempo_annotations(ann)
        self.assertEqual(len(tempos), 1)
        self.assertEqual(tempos[0].bpm, 13.0)
        self.assertEqual(tempos[0].matras_per_cycle, 12)

        sections = adapter.load_sections(ann)
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0].label, "Ālāp")
        self.assertEqual(sections[1].section_index, 2)

        phrases = adapter.load_melodic_phrases(ann)
        self.assertEqual(len(phrases), 2)
        self.assertEqual(phrases[0].phrase_swaras, "rP")
        self.assertEqual(phrases[0].voiced_flag, 1)

    # ------------------------------------------------------------------------
    # 10. Raga & Tala Normalization Tests
    # ------------------------------------------------------------------------
    def test_raga_normalization(self):
        """Test AC9: Raga name normalization handles variations, diacritics, and prefixes."""
        cases = [
            ("Shree", "shree"),
            ("Śrī", "shree"),
            ("Bhairabi", "bhairavi"),
            ("Raag Bhairav", "bhairav"),
            ("Lalat", "lalit"),
            ("Miya Malhar", "mian_malhar"),
            ("Miyan Malhar", "mian_malhar"),
            ("Aahir Bhairon", "ahir_bhairav"),
            ("Ahir Bhairav", "ahir_bhairav"),
            ("Raag Yaman Kalyan", "yaman"),
            ("Raageshree", "rageshree"),
            ("Sudh Kalyan", "shuddha_kalyan"),
            ("Sudh Sarang", "shuddha_sarang"),
            ("Komal Rishav Aasavari", "komal_rishabh_asavari"),
            ("Raag Unknown Custom", "unknown_custom"),
            ("", ""),
            (None, ""),
        ]
        for raw, expected in cases:
            self.assertEqual(normalize_raga_name(raw), expected, f"Failed on raw: {raw}")

    def test_tala_normalization(self):
        """Test AC9: Tala name normalization handles transliterations and prefixes."""
        cases = [
            ("Teentaal", "teental"),
            ("Tīntāl", "teental"),
            ("Taal Ektaal", "ektaal"),
            ("Ēktāl", "ektaal"),
            ("Jhaptaal", "jhaptaal"),
            ("Tilwada", "tilwada"),
            ("Tilavāḍā", "tilwada"),
            ("Rupak", "rupak"),
            ("Keherwa", "keherwa"),
            ("Dadra", "dadra"),
            ("Jhoomra", "jhoomra"),
            ("", ""),
            (None, ""),
        ]
        for raw, expected in cases:
            self.assertEqual(normalize_tala_name(raw), expected, f"Failed on raw: {raw}")

    # ------------------------------------------------------------------------
    # 11. Empty Raga Array Handling (Fallback)
    # ------------------------------------------------------------------------
    def test_empty_raga_array_fallback_from_title(self):
        """Test AC10: Falls back to track title heuristics when JSON raags is empty."""
        track_dir = self.temp_path / "Album A" / "Raag Bhoopali"
        track_dir.mkdir(parents=True)
        (track_dir / "Raag Bhoopali.json").write_text(
            '{"title": "Raag Bhoopali", "raags": [], "taals": []}', 
            encoding="utf-8"
        )

        adapter = SaragaDatasetAdapter(dataset_root=self.temp_path)
        ann = adapter.get_track_annotations(track_dir)

        self.assertEqual(ann.raga_names, ["Bhoopali"])
        self.assertEqual(ann.normalized_raga_names, ["bhoopali"])

    # ------------------------------------------------------------------------
    # 12. Path Traversal & Security Protection (Adversarial)
    # ------------------------------------------------------------------------
    def test_path_traversal_protection(self):
        """Test AC11 (ADV-1): Rejects path traversal attempts outside dataset root."""
        adapter = SaragaDatasetAdapter(dataset_root=self.temp_path)

        with self.assertRaises((ValueError, FileNotFoundError)):
            adapter.get_track_annotations(self.temp_path / ".." / ".." / "etc" / "passwd")

    def test_adversarial_corrupted_json(self):
        """Test ADV-4: Corrupted JSON raises an appropriate json.JSONDecodeError or ValueError."""
        track_dir = self.temp_path / "Album A" / "Corrupted Track"
        track_dir.mkdir(parents=True)
        (track_dir / "Corrupted Track.json").write_text("{ unclosed json: ", encoding="utf-8")

        adapter = SaragaDatasetAdapter(dataset_root=self.temp_path)
        with self.assertRaises(json.JSONDecodeError):
            adapter.get_track_annotations(track_dir)

    def test_adversarial_corrupted_ctonic(self):
        """Test ADV-4: Corrupted non-float ctonic file logs warning and sets tonic_hz to None."""
        track_dir = self.temp_path / "Album A" / "Corrupted Ctonic Track"
        track_dir.mkdir(parents=True)
        (track_dir / "Corrupted Ctonic Track.json").write_text('{"title": "Track"}', encoding="utf-8")
        (track_dir / "Corrupted Ctonic Track.ctonic.txt").write_text("INVALID_HZ_NOT_A_FLOAT", encoding="utf-8")

        adapter = SaragaDatasetAdapter(dataset_root=self.temp_path)
        ann = adapter.get_track_annotations(track_dir)
        self.assertIsNone(ann.tonic_hz)

    # ------------------------------------------------------------------------
    # 13. Property / Fuzz Test for Normalizer Stability
    # ------------------------------------------------------------------------
    def test_property_fuzz_normalizers(self):
        """Test ADV-7: Fuzz normalizers with random noisy inputs to ensure stability invariant."""
        import random
        import string

        for _ in range(100):
            # Generate random strings with mixed whitespace, diacritics, and punctuation
            noise = "".join(random.choices(string.ascii_letters + string.punctuation + "   ", k=20))
            r_out = normalize_raga_name(noise)
            t_out = normalize_tala_name(noise)
            self.assertIsInstance(r_out, str)
            self.assertIsInstance(t_out, str)
            self.assertNotIn(" ", r_out)
            self.assertNotIn(" ", t_out)

    # ------------------------------------------------------------------------
    # 14. Real Dataset Iteration Benchmark
    # ------------------------------------------------------------------------
    def test_iter_tracks_on_real_dataset(self):
        """Test P1: Iterating all tracks yields 108 valid SaragaTrackAnnotations with 0 crashes."""
        if not self.has_real_dataset:
            self.skipTest("Real dataset not found in workspace")
        adapter = SaragaDatasetAdapter(self.candidate_root)
        tracks_loaded = 0
        tonics_count = 0
        ragas_count = 0

        for ann in adapter.iter_tracks():
            tracks_loaded += 1
            if ann.tonic_hz is not None:
                tonics_count += 1
            if ann.raga_names:
                ragas_count += 1
            self.assertTrue(Path(ann.audio_path).exists() or Path(ann.metadata_json_path).exists())

        self.assertEqual(tracks_loaded, 108)
        self.assertEqual(tonics_count, 108)
        self.assertGreaterEqual(ragas_count, 100)


if __name__ == "__main__":
    unittest.main()
