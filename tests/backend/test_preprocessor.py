"""
Comprehensive test suite for AudioPreprocessor.
Tests format decoding, mono downmixing, 22050 Hz resampling, peak/silence normalization,
boundary conditions, corrupted/empty/missing files, duration limits, and invariants.
"""

import math
import os
import shutil
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from backend.app.analysis.preprocessor import (
    AudioPreprocessor,
    AudioPreprocessingResult,
    AudioPreprocessingError,
    AudioTooLongError,
    InvalidAudioError,
    HAS_SOUNDFILE,
)

try:
    import soundfile as sf
except ImportError:
    sf = None


def create_test_wav(
    file_path: Path,
    duration_s: float = 1.0,
    sample_rate: int = 44100,
    num_channels: int = 1,
    frequency_hz: float = 440.0,
    amplitude: float = 0.5,
    silence: bool = False,
):
    """Utility to generate uncompressed standard WAV files for tests."""
    num_samples = int(duration_s * sample_rate)
    t = np.linspace(0, duration_s, num_samples, endpoint=False)
    
    if silence:
        data = np.zeros(num_samples, dtype=np.float32)
    else:
        data = (amplitude * np.sin(2 * np.pi * frequency_hz * t)).astype(np.float32)

    if num_channels == 2:
        # Create stereo with distinct channel data (e.g., L = sine, R = 0.5 * sine)
        data = np.column_stack([data, data * 0.5])

    # Convert to 16-bit PCM for standard WAV compatibility
    int16_data = (data * 32767.0).astype(np.int16)
    wavfile.write(str(file_path), sample_rate, int16_data)


class TestAudioPreprocessor(unittest.TestCase):
    """Test suite for AudioPreprocessor."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.preprocessor = AudioPreprocessor()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------------
    # 1. Resampling to 22050 Hz
    # ------------------------------------------------------------------------
    def test_resample_to_22050_from_44100(self):
        """Test AC4: Resamples 44100 Hz input to 22050 Hz accurately."""
        wav_path = self.temp_path / "test_44100.wav"
        create_test_wav(wav_path, duration_s=1.0, sample_rate=44100, num_channels=1)

        result = self.preprocessor.process(wav_path)
        self.assertEqual(result.sample_rate, 22050)
        self.assertEqual(result.number_of_samples, 22050)
        self.assertAlmostEqual(result.duration_seconds, 1.0, places=2)
        self.assertEqual(result.waveform.dtype, np.float32)

    def test_resample_from_48000_and_16000(self):
        """Test AC4: Resamples from other standard rates (48000 Hz, 16000 Hz)."""
        for orig_sr in [48000, 16000]:
            wav_path = self.temp_path / f"test_{orig_sr}.wav"
            create_test_wav(wav_path, duration_s=0.5, sample_rate=orig_sr, num_channels=1)

            res = self.preprocessor.process(wav_path)
            self.assertEqual(res.sample_rate, 22050)
            self.assertEqual(res.number_of_samples, 11025)
            self.assertAlmostEqual(res.duration_seconds, 0.5, places=2)

    # ------------------------------------------------------------------------
    # 2. Mono & Stereo Conversion
    # ------------------------------------------------------------------------
    def test_mono_conversion(self):
        """Test AC2: Mono input preserved as 1D mono waveform."""
        wav_path = self.temp_path / "mono.wav"
        create_test_wav(wav_path, duration_s=1.0, sample_rate=22050, num_channels=1)

        res = self.preprocessor.process(wav_path)
        self.assertEqual(res.channels_original, 1)
        self.assertEqual(res.waveform.ndim, 1)

    def test_stereo_conversion(self):
        """Test AC3: Stereo input correctly downmixed to 1D mono."""
        wav_path = self.temp_path / "stereo.wav"
        create_test_wav(wav_path, duration_s=1.0, sample_rate=22050, num_channels=2)

        res = self.preprocessor.process(wav_path)
        self.assertEqual(res.channels_original, 2)
        self.assertEqual(res.waveform.ndim, 1)
        self.assertGreater(res.rms, 0.0)

    # ------------------------------------------------------------------------
    # 3. Silent Audio & Normalization
    # ------------------------------------------------------------------------
    def test_silent_audio_normalization(self):
        """Test AC5: Silent audio does not cause division by zero or NaN."""
        wav_path = self.temp_path / "silent.wav"
        create_test_wav(wav_path, duration_s=1.0, sample_rate=22050, silence=True)

        res = self.preprocessor.process(wav_path)
        self.assertTrue(res.is_silent)
        self.assertEqual(res.peak_amplitude, 0.0)
        self.assertEqual(res.rms, 0.0)
        self.assertTrue(np.all(np.isfinite(res.waveform)))

    def test_peak_normalization_headroom(self):
        """Test AC6: Non-silent audio normalized to 0.99 peak (-0.1 dB headroom)."""
        wav_path = self.temp_path / "normal.wav"
        create_test_wav(wav_path, duration_s=0.5, sample_rate=22050, amplitude=0.3)

        res = self.preprocessor.process(wav_path)
        self.assertFalse(res.is_silent)
        self.assertAlmostEqual(res.peak_amplitude, 0.99, places=2)
        self.assertTrue(np.all(np.abs(res.waveform) <= 1.0))

    # ------------------------------------------------------------------------
    # 4. Error & Boundary Conditions
    # ------------------------------------------------------------------------
    def test_missing_file(self):
        """Test AC8: Missing audio file raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            self.preprocessor.process(self.temp_path / "non_existent.wav")

    def test_empty_file(self):
        """Test AC6: 0-byte file raises InvalidAudioError."""
        empty_file = self.temp_path / "empty.wav"
        empty_file.touch()

        with self.assertRaises(InvalidAudioError):
            self.preprocessor.process(empty_file)

    def test_corrupted_audio(self):
        """Test AC7: Corrupted non-audio bytes raise InvalidAudioError."""
        corrupt_file = self.temp_path / "corrupt.wav"
        corrupt_file.write_bytes(b"NOT_A_VALID_WAV_HEADER_CORRUPTED_STREAM")

        with self.assertRaises(InvalidAudioError):
            self.preprocessor.process(corrupt_file)

    def test_duration_exceeding_10_minutes(self):
        """Test AC9: Audio duration > 600s raises AudioTooLongError."""
        proc_short = AudioPreprocessor(max_duration_seconds=2.0)
        wav_path = self.temp_path / "too_long.wav"
        create_test_wav(wav_path, duration_s=3.0, sample_rate=22050)

        with self.assertRaises(AudioTooLongError):
            proc_short.process(wav_path)

    def test_very_short_audio(self):
        """Test AC11: Handles tiny audio clips (50 ms) without crashing."""
        wav_path = self.temp_path / "short.wav"
        create_test_wav(wav_path, duration_s=0.05, sample_rate=22050)

        res = self.preprocessor.process(wav_path)
        self.assertEqual(res.number_of_samples, int(0.05 * 22050))
        self.assertAlmostEqual(res.duration_seconds, 0.05, places=2)

    # ------------------------------------------------------------------------
    # 5. Determinism & Invariants
    # ------------------------------------------------------------------------
    def test_deterministic_repeated_processing(self):
        """Test AC10: Repeated processing yields identical bit-level waveforms."""
        wav_path = self.temp_path / "det.wav"
        create_test_wav(wav_path, duration_s=0.5, sample_rate=44100, frequency_hz=330.0)

        res1 = self.preprocessor.process(wav_path)
        res2 = self.preprocessor.process(wav_path)

        np.testing.assert_array_equal(res1.waveform, res2.waveform)
        self.assertEqual(res1.peak_amplitude, res2.peak_amplitude)
        self.assertEqual(res1.rms, res2.rms)

    # ------------------------------------------------------------------------
    # 6. Property / Fuzz Test
    # ------------------------------------------------------------------------
    def test_property_invariants_fuzz(self):
        """Test Invariant: Waveform is always finite, float32, sr=22050, duration <= 600s."""
        import random

        for i in range(10):
            dur = random.uniform(0.01, 2.0)
            sr = random.choice([8000, 16000, 22050, 44100, 48000])
            ch = random.choice([1, 2])
            amp = random.uniform(0.0, 1.0)
            freq = random.uniform(100.0, 2000.0)

            p = self.temp_path / f"fuzz_{i}.wav"
            create_test_wav(p, duration_s=dur, sample_rate=sr, num_channels=ch, frequency_hz=freq, amplitude=amp)

            res = self.preprocessor.process(p)

            self.assertEqual(res.sample_rate, 22050)
            self.assertEqual(res.waveform.dtype, np.float32)
            self.assertTrue(np.all(np.isfinite(res.waveform)))
            self.assertLessEqual(res.duration_seconds, 600.0)
            self.assertLessEqual(res.peak_amplitude, 1.0)
            self.assertGreaterEqual(res.peak_amplitude, 0.0)

    # ------------------------------------------------------------------------
    # 7. Metadata Serialization
    # ------------------------------------------------------------------------
    def test_metadata_dict_serialization(self):
        """Test to_metadata_dict format."""
        wav_path = self.temp_path / "meta.wav"
        create_test_wav(wav_path, duration_s=0.5, sample_rate=22050)

        res = self.preprocessor.process(wav_path)
        meta = res.to_metadata_dict()

        self.assertIn("file_path", meta)
        self.assertEqual(meta["sample_rate"], 22050)
        self.assertEqual(meta["duration_seconds"], 0.5)
    # ------------------------------------------------------------------------
    # 8. Real Saraga MP3 Integration Test
    # ------------------------------------------------------------------------
    def test_real_saraga_mp3_processing(self):
        """Test AC1: Processes an actual Saraga Hindustani .mp3.mp3 track successfully."""
        workspace_root = Path(__file__).resolve().parents[2]
        dataset_root = workspace_root / "saraga1.5_hindustani" / "saraga1.5_hindustani"
        if not dataset_root.exists():
            self.skipTest("Saraga dataset not present in workspace")

        # Find any Saraga track <= 600s
        target_mp3 = None
        for mp3_candidate in dataset_root.glob("*/*/*.mp3.mp3"):
            info = sf.info(str(mp3_candidate))
            if info.duration <= 600.0:
                target_mp3 = mp3_candidate
                break

        if not target_mp3:
            self.skipTest("No Saraga track under 600s found")

        res = self.preprocessor.process(target_mp3)
        self.assertEqual(res.sample_rate, 22050)
        self.assertEqual(res.waveform.ndim, 1)
        self.assertEqual(res.waveform.dtype, np.float32)
        self.assertAlmostEqual(res.peak_amplitude, 0.99, places=2)
        self.assertGreater(res.rms, 0.0)
        self.assertFalse(res.is_silent)
        self.assertTrue(np.all(np.isfinite(res.waveform)))


if __name__ == "__main__":
    unittest.main()
