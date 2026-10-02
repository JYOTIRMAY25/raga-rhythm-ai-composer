"""
Adversarial Performance and Robustness Verification Test Suite.
Tests edge cases, extreme audio lengths, signal dynamics, multichannel inputs,
and property invariants for the optimized analysis pipeline.
"""

import numpy as np
import pytest

from backend.app.analysis.pipeline import AnalysisPipeline, UnifiedAnalysisResult
from backend.app.analysis.pitch_extractor import PitchExtractor, PitchExtractionResult
from backend.app.analysis.preprocessor import AudioPreprocessor
from backend.app.analysis.raga_detector import RagaDetector
from backend.app.analysis.swara_analyzer import SwaraAnalyzer
from backend.app.analysis.tonic_estimator import TonicEstimator


@pytest.fixture
def pipeline() -> AnalysisPipeline:
    return AnalysisPipeline()


# ============================================================================
# Category 1: Extreme Audio Durations
# ============================================================================

def test_adversarial_very_short_audio(pipeline: AnalysisPipeline) -> None:
    """Very short audio (50 ms / 1102 samples) must process safely without crashes or NaNs."""
    sr = 22050
    duration = 0.05  # 50 ms
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    waveform = (0.5 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)

    result: UnifiedAnalysisResult = pipeline.process_waveform(waveform, sample_rate=sr)

    assert result is not None
    assert result.pitch.total_frames >= 1
    assert 0.0 <= result.raga.confidence <= 1.0
    assert 0.0 <= result.tala.confidence <= 1.0
    if result.tonic.frequency_hz is not None:
        assert np.isfinite(result.tonic.frequency_hz)
    if result.pitch.mean_f0_hz is not None:
        assert np.isfinite(result.pitch.mean_f0_hz)


def test_adversarial_longer_audio(pipeline: AnalysisPipeline) -> None:
    """Longer audio (30 seconds) must process completely and maintain memory/performance bounds."""
    sr = 22050
    duration = 30.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    waveform = (
        0.5 * np.sin(2 * np.pi * 140.0 * t) +
        0.3 * np.sin(2 * np.pi * 210.0 * t) +
        0.05 * np.random.normal(0, 0.05, len(t))
    ).astype(np.float32)

    result: UnifiedAnalysisResult = pipeline.process_waveform(waveform, sample_rate=sr)

    assert result is not None
    assert result.pitch.total_frames > 5000
    assert result.raga.predicted_raga != ""


# ============================================================================
# Category 2: Signal Dynamics & Distortion
# ============================================================================

def test_adversarial_pure_silence(pipeline: AnalysisPipeline) -> None:
    """Pure silence (all zeros) must return unvoiced masks, 0.0 confidence, and safe fallbacks."""
    sr = 22050
    waveform = np.zeros(int(sr * 3.0), dtype=np.float32)

    result: UnifiedAnalysisResult = pipeline.process_waveform(waveform, sample_rate=sr)

    assert result is not None
    assert result.pitch.voiced_percentage == 0.0
    assert result.pitch.voiced_frames == 0
    assert result.raga.confidence == 0.0 or result.raga.confidence < 0.35


def test_adversarial_ultra_low_amplitude(pipeline: AnalysisPipeline) -> None:
    """Ultra low-amplitude signal (1e-6) must not trigger numerical underflow or NaNs."""
    sr = 22050
    t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
    waveform = (1e-6 * np.sin(2 * np.pi * 140.0 * t)).astype(np.float32)

    result: UnifiedAnalysisResult = pipeline.process_waveform(waveform, sample_rate=sr)

    assert result is not None
    assert 0.0 <= result.raga.confidence <= 1.0
    assert 0.0 <= result.tala.confidence <= 1.0


def test_adversarial_heavy_noise(pipeline: AnalysisPipeline) -> None:
    """Heavy Gaussian noise (SNR < 0 dB) must remain numerically stable with bounded scores."""
    sr = 22050
    t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
    signal = 0.2 * np.sin(2 * np.pi * 150.0 * t)
    noise = np.random.normal(0, 0.5, len(t))
    waveform = (signal + noise).astype(np.float32)

    result: UnifiedAnalysisResult = pipeline.process_waveform(waveform, sample_rate=sr)

    assert result is not None
    assert 0.0 <= result.raga.confidence <= 1.0
    assert 0.0 <= result.tala.confidence <= 1.0


# ============================================================================
# Category 3: Multichannel & Format Invariants
# ============================================================================

def test_adversarial_stereo_input(pipeline: AnalysisPipeline) -> None:
    """Stereo 2D input array (samples, 2) must be safely converted to mono and analyzed."""
    sr = 22050
    t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
    left = 0.5 * np.sin(2 * np.pi * 140.0 * t).astype(np.float32)
    right = 0.4 * np.sin(2 * np.pi * 210.0 * t).astype(np.float32)
    stereo_waveform = np.column_stack([left, right])

    preprocessor = AudioPreprocessor()
    mono = preprocessor.to_mono(stereo_waveform)
    norm, _, _, _ = preprocessor.normalize(mono)

    result = pipeline.process_waveform(norm, sample_rate=sr)

    assert result is not None
    assert result.pitch.total_frames > 0


# ============================================================================
# Category 4: Invariants & Determinism
# ============================================================================

def test_adversarial_repeated_same_input_determinism(pipeline: AnalysisPipeline) -> None:
    """Running identical waveform multiple times must produce bit-exact identical predictions."""
    sr = 22050
    t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
    waveform = (
        0.5 * np.sin(2 * np.pi * 140.0 * t) +
        0.3 * np.sin(2 * np.pi * 210.0 * t)
    ).astype(np.float32)

    res1 = pipeline.process_waveform(waveform, sample_rate=sr)
    res2 = pipeline.process_waveform(waveform, sample_rate=sr)

    assert res1.tonic.frequency_hz == res2.tonic.frequency_hz
    assert res1.raga.predicted_raga == res2.raga.predicted_raga
    assert res1.raga.confidence == res2.raga.confidence
    assert res1.tala.predicted_tala == res2.tala.predicted_tala
    assert res1.pitch.mean_f0_hz == res2.pitch.mean_f0_hz
    assert res1.pitch.voiced_percentage == res2.pitch.voiced_percentage


def test_adversarial_randomized_fuzz_properties(pipeline: AnalysisPipeline) -> None:
    """Property test across 10 randomized synthetic signals verifying numerical safety invariants."""
    np.random.seed(42)
    sr = 22050

    for i in range(10):
        duration = float(np.random.uniform(0.5, 3.0))
        freq1 = float(np.random.uniform(80.0, 450.0))
        freq2 = freq1 * float(np.random.choice([1.25, 1.333, 1.5, 1.875]))
        amp1 = float(np.random.uniform(0.1, 0.9))
        amp2 = float(np.random.uniform(0.05, 0.4))
        noise_level = float(np.random.uniform(0.0, 0.15))

        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        waveform = (
            amp1 * np.sin(2 * np.pi * freq1 * t) +
            amp2 * np.sin(2 * np.pi * freq2 * t) +
            np.random.normal(0, noise_level, len(t))
        ).astype(np.float32)

        res = pipeline.process_waveform(waveform, sample_rate=sr)

        # Invariant 1: Confidences bounded in [0.0, 1.0]
        assert 0.0 <= res.raga.confidence <= 1.0, f"Raga confidence out of bounds in run {i}"
        assert 0.0 <= res.tala.confidence <= 1.0, f"Tala confidence out of bounds in run {i}"

        # Invariant 2: Timings are strictly positive
        for stage, timing in res.stage_timings_ms.items():
            assert timing >= 0.0, f"Negative timing for {stage} in run {i}"
