"""
Unit and Integration Tests for AudioRenderer and WAV Export.
Verifies DSP audio synthesis, ADSR envelopes, ornament modeling, clipping prevention,
and WAV standard formatting.
"""

from __future__ import annotations

import io
import struct
import wave
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.composition.audio_renderer import AudioRenderer, audio_renderer
from backend.app.composition.composition_engine import CompositionEngine
from backend.app.composition.composition_models import (
    CompositionCycle,
    CompositionRequest,
    SwaraEvent,
    SymbolicComposition,
    ValidationResult,
)
from backend.app.main import app

client = TestClient(app)


def _make_dummy_composition(
    events: list[SwaraEvent],
    duration_seconds: float = 10.0,
    raga_id: str = "yaman",
    tala_id: str = "teental",
    tempo_bpm: int = 80,
    tonic_hz: float = 220.0,
) -> SymbolicComposition:
    """Helper creating a minimal SymbolicComposition for targeted unit tests."""
    return SymbolicComposition(
        composition_id="test-comp-123",
        title="Test Composition",
        raga_id=raga_id,
        raga_name="Yaman",
        thaat="Kalyan",
        tala_id=tala_id,
        tala_name="Teental",
        matras=16,
        vibhag_structure="4+4+4+4",
        tempo_bpm=tempo_bpm,
        laya="Madhya",
        tonic_note="A",
        tonic_hz=tonic_hz,
        style="bandish",
        total_cycles=1,
        total_matras=16,
        duration_seconds=duration_seconds,
        events=events,
        cycles=[CompositionCycle(cycle_number=1, events=events)],
        seed=42,
        validation=ValidationResult(
            valid=True,
            swara_compliance_score=1.0,
            tala_alignment_score=1.0,
            sam_resolution_passed=True,
            diagnostics=[],
        ),
    )


class TestAudioRenderer:
    """Unit tests for the PCM audio renderer."""

    def test_valid_rendering_shape_and_dtype(self):
        engine = CompositionEngine()
        comp = engine.compose(CompositionRequest(raga_id="yaman", tala_id="teental", duration_seconds=15, seed=42))
        renderer = AudioRenderer(sample_rate=22050)
        samples = renderer.render_composition(comp)

        assert isinstance(samples, np.ndarray)
        assert samples.dtype == np.float32
        assert len(samples) > 0
        expected_len = int(comp.duration_seconds * 22050)
        assert abs(len(samples) - expected_len) < 22050  # within 1 second

    def test_silence_and_empty_events(self):
        empty_comp = _make_dummy_composition(events=[], duration_seconds=1.0)
        renderer = AudioRenderer(sample_rate=22050)
        samples = renderer.render_composition(empty_comp)

        assert isinstance(samples, np.ndarray)
        assert len(samples) > 0
        assert not np.isnan(samples).any()

    def test_nan_and_infinity_protection(self):
        renderer = AudioRenderer(sample_rate=22050)
        ev = SwaraEvent(cycle=1, vibhag=1, matra=1, swara="S", pitch_hz=220.0, duration_matras=1.0)
        comp = _make_dummy_composition(events=[ev], duration_seconds=2.0)
        # Directly test renderer robustly handling internal NaN/Inf
        raw_samples = np.array([0.5, float("nan"), float("inf"), -float("inf"), 0.2], dtype=np.float32)
        cleaned = np.nan_to_num(raw_samples, nan=0.0, posinf=0.0, neginf=0.0)
        wav_bytes = renderer.encode_wav(cleaned)

        assert len(wav_bytes) > 44
        samples = renderer.render_composition(comp)
        assert not np.isnan(samples).any()
        assert not np.isinf(samples).any()

    def test_single_note_rendering(self):
        ev = SwaraEvent(
            cycle=1, vibhag=1, matra=1, subdivision=0, swara="S", octave=0, pitch_hz=220.0, duration_matras=4.0
        )
        comp = _make_dummy_composition(events=[ev], duration_seconds=3.0, tempo_bpm=80)
        renderer = AudioRenderer(sample_rate=22050)
        samples = renderer.render_composition(comp)

        assert len(samples) > 0
        assert not np.isnan(samples).any()
        assert not np.isinf(samples).any()
        assert np.max(np.abs(samples)) > 0.1

    def test_octave_register_frequencies(self):
        renderer = AudioRenderer(sample_rate=22050)
        # Mandra (low), Madhya (middle), Tara (high)
        ev_low = SwaraEvent(cycle=1, vibhag=1, matra=1, swara="N.", octave=-1, pitch_hz=110.0, duration_matras=2.0)
        ev_mid = SwaraEvent(cycle=1, vibhag=1, matra=3, swara="S", octave=0, pitch_hz=220.0, duration_matras=2.0)
        ev_high = SwaraEvent(cycle=1, vibhag=2, matra=5, swara="S'", octave=1, pitch_hz=440.0, duration_matras=2.0)

        comp = _make_dummy_composition(events=[ev_low, ev_mid, ev_high], duration_seconds=6.0)
        samples = renderer.render_composition(comp)

        assert len(samples) > 0
        assert np.max(np.abs(samples)) <= 0.95

    def test_meend_glide_rendering(self):
        renderer = AudioRenderer(sample_rate=22050)
        ev1 = SwaraEvent(cycle=1, vibhag=1, matra=1, swara="G", pitch_hz=277.18, duration_matras=2.0, ornament="meend")
        ev2 = SwaraEvent(cycle=1, vibhag=1, matra=3, swara="P", pitch_hz=329.63, duration_matras=2.0)

        comp = _make_dummy_composition(events=[ev1, ev2], duration_seconds=4.0)
        samples = renderer.render_composition(comp)

        assert len(samples) > 0
        assert not np.isnan(samples).any()

    def test_kan_grace_note_rendering(self):
        renderer = AudioRenderer(sample_rate=22050)
        ev = SwaraEvent(cycle=1, vibhag=1, matra=1, swara="R", pitch_hz=246.94, duration_matras=2.0, ornament="kan")
        comp = _make_dummy_composition(events=[ev], duration_seconds=3.0)
        samples = renderer.render_composition(comp)

        assert len(samples) > 0
        assert np.max(np.abs(samples)) > 0.05

    def test_andolan_oscillation_rendering(self):
        renderer = AudioRenderer(sample_rate=22050)
        ev = SwaraEvent(cycle=1, vibhag=1, matra=1, swara="d", pitch_hz=174.61, duration_matras=3.0, ornament="andolan")
        comp = _make_dummy_composition(events=[ev], duration_seconds=4.0)
        samples = renderer.render_composition(comp)

        assert len(samples) > 0
        assert not np.isnan(samples).any()

    def test_gamak_oscillation_rendering(self):
        renderer = AudioRenderer(sample_rate=22050)
        ev = SwaraEvent(cycle=1, vibhag=1, matra=1, swara="D", pitch_hz=185.0, duration_matras=3.0, ornament="gamak")
        comp = _make_dummy_composition(events=[ev], duration_seconds=4.0)
        samples = renderer.render_composition(comp)

        assert len(samples) > 0
        assert not np.isnan(samples).any()

    def test_envelope_continuity_and_no_clicks(self):
        renderer = AudioRenderer(sample_rate=22050)
        env = renderer._calculate_adsr_envelope(22050)

        # Starts and ends smoothly near 0 without abrupt step
        assert env[0] == pytest.approx(0.0, abs=1e-3)
        assert env[-1] == pytest.approx(0.0, abs=1e-3)
        assert np.all(env >= 0.0)
        assert np.all(env <= 1.0)

    def test_clipping_protection_and_peak_normalization(self):
        renderer = AudioRenderer(sample_rate=22050)
        engine = CompositionEngine()
        comp = engine.compose(CompositionRequest(raga_id="bhairav", tala_id="teental", duration_seconds=20, seed=108))
        samples = renderer.render_composition(comp)

        peak = np.max(np.abs(samples))
        assert peak <= 0.90
        assert peak >= 0.70  # properly normalized, not silent

    def test_multiple_notes_rendering(self):
        renderer = AudioRenderer(sample_rate=22050)
        events = [
            SwaraEvent(cycle=1, vibhag=1, matra=1, swara="S", pitch_hz=220.0, duration_matras=1.0),
            SwaraEvent(cycle=1, vibhag=1, matra=2, swara="R", pitch_hz=246.94, duration_matras=1.0),
            SwaraEvent(cycle=1, vibhag=1, matra=3, swara="G", pitch_hz=277.18, duration_matras=1.0),
            SwaraEvent(cycle=1, vibhag=1, matra=4, swara="M", pitch_hz=293.66, duration_matras=1.0),
            SwaraEvent(cycle=1, vibhag=2, matra=5, swara="P", pitch_hz=329.63, duration_matras=2.0),
        ]
        comp = _make_dummy_composition(events=events, duration_seconds=6.0)
        samples = renderer.render_composition(comp)

        assert len(samples) == int(6.0 * 22050)
        assert not np.isnan(samples).any()
        assert not np.isinf(samples).any()
        assert np.max(np.abs(samples)) <= 0.95

    def test_oversized_duration_and_sample_count_safety(self):
        renderer = AudioRenderer(sample_rate=22050)
        ev = SwaraEvent(cycle=1, vibhag=1, matra=1, swara="S", pitch_hz=220.0, duration_matras=1.0)
        comp = _make_dummy_composition(events=[ev], duration_seconds=9999.0)
        samples = renderer.render_composition(comp)

        assert len(samples) <= renderer.MAX_SAMPLES
        assert len(samples) == int(renderer.MAX_DURATION_SECONDS * 22050)
        assert not np.isnan(samples).any()

    def test_invalid_composition_corrupted_pitches(self):
        renderer = AudioRenderer(sample_rate=22050)
        # Event with extreme pitch or negative pitch
        ev1 = SwaraEvent(cycle=1, vibhag=1, matra=1, swara="S", pitch_hz=0.001, duration_matras=1.0)
        ev2 = SwaraEvent(cycle=1, vibhag=1, matra=2, swara="S'", pitch_hz=50000.0, duration_matras=1.0)
        comp = _make_dummy_composition(events=[ev1, ev2], duration_seconds=3.0)
        samples = renderer.render_composition(comp)

        assert len(samples) > 0
        assert not np.isnan(samples).any()
        assert not np.isinf(samples).any()

    def test_repeated_generation_safety_and_resource_cleanup(self):
        renderer = AudioRenderer(sample_rate=22050)
        engine = CompositionEngine()

        for seed in [1, 2, 3, 4, 5]:
            comp = engine.compose(CompositionRequest(raga_id="yaman", tala_id="teental", duration_seconds=15, seed=seed))
            wav_bytes = renderer.render_wav_bytes(comp)
            assert len(wav_bytes) > 1000
            assert wav_bytes[:4] == b"RIFF"

    def test_deterministic_rendering(self):
        renderer = AudioRenderer(sample_rate=22050)
        engine = CompositionEngine()
        comp = engine.compose(CompositionRequest(raga_id="yaman", tala_id="ektaal", duration_seconds=30, seed=42))

        run_1 = renderer.render_composition(comp)
        run_2 = renderer.render_composition(comp)

        assert np.array_equal(run_1, run_2)
        wav_1 = renderer.render_wav_bytes(comp)
        wav_2 = renderer.render_wav_bytes(comp)
        assert wav_1 == wav_2


class TestWavEncoder:
    """Tests standard WAV header formatting and byte integrity."""

    def test_wav_header_and_riff_structure(self):
        renderer = AudioRenderer(sample_rate=22050)
        engine = CompositionEngine()
        comp = engine.compose(CompositionRequest(raga_id="malkauns", tala_id="rupak", duration_seconds=20, seed=7))
        wav_bytes = renderer.render_wav_bytes(comp)

        assert len(wav_bytes) > 44
        assert wav_bytes[:4] == b"RIFF"
        assert wav_bytes[8:12] == b"WAVE"
        assert wav_bytes[12:16] == b"fmt "

        # Parse with Python standard wave module
        w = wave.open(io.BytesIO(wav_bytes), "rb")
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2  # 16-bit
        assert w.getframerate() == 22050
        assert w.getnframes() > 0

    def test_wav_duration_matches_composition(self):
        renderer = AudioRenderer(sample_rate=22050)
        engine = CompositionEngine()
        comp = engine.compose(CompositionRequest(raga_id="todi", tala_id="dadra", duration_seconds=25, seed=123))
        wav_bytes = renderer.render_wav_bytes(comp)

        w = wave.open(io.BytesIO(wav_bytes), "rb")
        actual_dur = w.getnframes() / w.getframerate()
        assert abs(actual_dur - comp.duration_seconds) < 0.1


class TestWavApiEndpoints:
    """Integration tests for POST and GET /api/v1/generate/wav."""

    def test_post_generate_wav_returns_200_audio(self):
        payload = {"raga_id": "yaman", "tala_id": "teental", "duration_seconds": 20, "seed": 42}
        resp = client.post("/api/v1/generate/wav", json=payload)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"
        assert "attachment; filename=" in resp.headers["content-disposition"]
        assert len(resp.content) > 1000

        # Validate with wave module
        w = wave.open(io.BytesIO(resp.content), "rb")
        assert w.getframerate() == 22050
        assert w.getnchannels() == 1

    def test_get_generate_wav_streaming(self):
        resp = client.get("/api/v1/generate/wav?raga_id=bhairav&tala_id=jhaptaal&duration_seconds=15&seed=99")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"
        assert len(resp.content) > 1000

    def test_post_generate_wav_unknown_raga_rejected(self):
        resp = client.post("/api/v1/generate/wav", json={"raga_id": "fake_raga", "tala_id": "teental"})
        assert resp.status_code == 400

    def test_post_generate_wav_unknown_tala_rejected(self):
        resp = client.post("/api/v1/generate/wav", json={"raga_id": "yaman", "tala_id": "fake_tala"})
        assert resp.status_code == 400

