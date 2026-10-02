"""
Comprehensive Unit, Integration, and Property Tests for Phase 4B:
Microtonal Shruti Tuning, Expression Controller, and Timbral Synthesizer.
"""

from __future__ import annotations

import math
import random
import numpy as np
import pytest

from backend.app.composition.audio_renderer import AudioRenderer, audio_renderer
from backend.app.composition.composition_engine import CompositionEngine
from backend.app.composition.composition_models import (
    CompositionCycle,
    CompositionRequest,
    SwaraEvent,
    SymbolicComposition,
    ValidationResult,
)
from backend.app.composition.expression import ExpressionController, expression_controller
from backend.app.composition.raga_constraints import SEMITONE_OFFSETS
from backend.app.composition.shruti import (
    DOCUMENTED_RAGA_PROFILES,
    IntonationProfile,
    ShrutiMapper,
    ShrutiPitch,
    cents_to_hz,
    cents_to_ratio,
    hz_to_cents_offset,
    ratio_to_cents,
    shruti_mapper,
)
from backend.app.composition.timbre import TIMBRE_PROFILES, TimbralSynthesizer, timbral_synthesizer


def _create_test_composition(
    events: list[SwaraEvent],
    raga_id: str = "yaman",
    tala_id: str = "teental",
    duration_seconds: float = 10.0,
    tonic_hz: float = 138.59,
) -> SymbolicComposition:
    return SymbolicComposition(
        composition_id="test-shruti-101",
        title="Test Shruti Composition",
        raga_id=raga_id,
        raga_name=raga_id.title(),
        thaat="Kalyan",
        tala_id=tala_id,
        tala_name=tala_id.title(),
        matras=16,
        vibhag_structure="4+4+4+4",
        tempo_bpm=84,
        laya="Madhya",
        tonic_note="C#",
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


# ============================================================================
# 1. Mathematical Conversion & Base Intonation Tests
# ============================================================================

class TestShrutiMathAndBaseIntonation:
    """Verifies logarithmic cents conversion, frequency math, and tonic exactness."""

    def test_cents_and_ratio_bidirectional_consistency(self):
        cents_values = [0.0, 100.0, 203.91, 386.31, 701.96, 1200.0, -13.69, 11.73]
        for c in cents_values:
            ratio = cents_to_ratio(c)
            recovered_cents = ratio_to_cents(ratio)
            assert recovered_cents == pytest.approx(c, abs=1e-4)

    def test_frequency_conversion_utilities(self):
        base_hz = 220.0
        # +1200 cents must equal exact 2.0x octave
        octave_hz = cents_to_hz(base_hz, 1200.0)
        assert octave_hz == pytest.approx(440.0, rel=1e-5)

        # 0 cents must equal base frequency
        same_hz = cents_to_hz(base_hz, 0.0)
        assert same_hz == pytest.approx(220.0, rel=1e-5)

        offset = hz_to_cents_offset(220.0, 440.0)
        assert offset == pytest.approx(1200.0, abs=1e-4)

    def test_sa_exactness_under_all_tuning_modes(self):
        tonic_hz = 138.59
        for mode in ["canonical", "raga_aware"]:
            for raga in ["yaman", "bhairav", "todi", "darbari_kanhada", "malkauns", "unknown_raga"]:
                pitch = shruti_mapper.map_pitch("S", tonic_hz=tonic_hz, raga_id=raga, tuning_mode=mode)
                assert pitch.final_frequency == pytest.approx(tonic_hz, rel=1e-5)
                assert pitch.cents_offset == 0.0
                assert pitch.swara == "S"

    def test_octave_equivalence(self):
        tonic_hz = 138.59
        p_low = shruti_mapper.map_pitch("S.", tonic_hz=tonic_hz, raga_id="yaman", tuning_mode="canonical")
        p_mid = shruti_mapper.map_pitch("S", tonic_hz=tonic_hz, raga_id="yaman", tuning_mode="canonical")
        p_high = shruti_mapper.map_pitch("S'", tonic_hz=tonic_hz, raga_id="yaman", tuning_mode="canonical")

        assert p_low.final_frequency == pytest.approx(tonic_hz * 0.5, rel=1e-5)
        assert p_mid.final_frequency == pytest.approx(tonic_hz, rel=1e-5)
        assert p_high.final_frequency == pytest.approx(tonic_hz * 2.0, rel=1e-5)


# ============================================================================
# 2. Raga Profiles & Canonical Fallback Tests
# ============================================================================

class TestRagaIntonationProfiles:
    """Verifies documented shruti intervals and explicit fallback behavior."""

    def test_canonical_fallback_when_tuning_mode_canonical(self):
        tonic_hz = 220.0
        # Even for Yaman, in canonical mode cents_offset must be 0.0
        pitch = shruti_mapper.map_pitch("G", tonic_hz=tonic_hz, raga_id="yaman", tuning_mode="canonical")
        canonical_g = tonic_hz * (2.0 ** (4.0 / 12.0))
        assert pitch.final_frequency == pytest.approx(canonical_g, rel=1e-5)
        assert pitch.cents_offset == 0.0
        assert pitch.source == "canonical_12tet"

    def test_explicit_yaman_just_intonation(self):
        tonic_hz = 200.0
        pitch_g = shruti_mapper.map_pitch("G", tonic_hz=tonic_hz, raga_id="yaman", tuning_mode="raga_aware")
        # 5/4 Just third = 250.0 Hz (-13.69 cents from 12-TET 251.98 Hz)
        assert pitch_g.cents_offset == pytest.approx(-13.69, abs=0.1)
        assert pitch_g.final_frequency == pytest.approx(200.0 * 1.25, rel=1e-3)
        assert pitch_g.ratio_str == "5/4"

        pitch_m = shruti_mapper.map_pitch("M", tonic_hz=tonic_hz, raga_id="yaman", tuning_mode="raga_aware")
        # 45/32 Just augmented fourth = 281.25 Hz (-9.78 cents)
        assert pitch_m.cents_offset == pytest.approx(-9.78, abs=0.1)
        assert pitch_m.final_frequency == pytest.approx(200.0 * (45.0 / 32.0), rel=1e-3)

    def test_explicit_bhairav_microtonal_intonation(self):
        tonic_hz = 200.0
        pitch_r = shruti_mapper.map_pitch("r", tonic_hz=tonic_hz, raga_id="bhairav", tuning_mode="raga_aware")
        # 16/15 komal Re (+11.73 cents)
        assert pitch_r.cents_offset == pytest.approx(11.73, abs=0.1)
        assert pitch_r.final_frequency == pytest.approx(200.0 * (16.0 / 15.0), rel=1e-3)

        pitch_d = shruti_mapper.map_pitch("d", tonic_hz=tonic_hz, raga_id="bhairav", tuning_mode="raga_aware")
        # 8/5 komal Dha (+13.69 cents)
        assert pitch_d.cents_offset == pytest.approx(13.69, abs=0.1)
        assert pitch_d.final_frequency == pytest.approx(200.0 * (8.0 / 5.0), rel=1e-3)

    def test_explicit_todi_ati_komal_intonation(self):
        tonic_hz = 200.0
        pitch_r = shruti_mapper.map_pitch("r", tonic_hz=tonic_hz, raga_id="todi", tuning_mode="raga_aware")
        # 256/243 Ati-komal Re (-9.78 cents)
        assert pitch_r.cents_offset == pytest.approx(-9.78, abs=0.1)
        assert pitch_r.final_frequency == pytest.approx(200.0 * (256.0 / 243.0), rel=1e-3)

    def test_missing_raga_graceful_fallback(self):
        tonic_hz = 150.0
        # Undocumented raga returns exact canonical mapping with 0.0 cents offset
        pitch = shruti_mapper.map_pitch("G", tonic_hz=tonic_hz, raga_id="undocumented_raga_xyz", tuning_mode="raga_aware")
        canonical_g = tonic_hz * (2.0 ** (4.0 / 12.0))
        assert pitch.final_frequency == pytest.approx(canonical_g, rel=1e-5)
        assert pitch.cents_offset == 0.0
        assert pitch.source == "canonical_12tet"


# ============================================================================
# 3. Contextual Intonation & Direction Tests
# ============================================================================

class TestContextualIntonation:
    """Verifies melodic context adjustments (ascending, descending, cadential resolution)."""

    def test_ascending_direction_inflection(self):
        tonic_hz = 200.0
        # Ascending movement adds +2.5 cents brightness
        p_asc = shruti_mapper.map_pitch(
            "N", tonic_hz=tonic_hz, raga_id="yaman", tuning_mode="raga_aware",
            next_swara="S", is_ascending=True
        )
        p_desc = shruti_mapper.map_pitch(
            "N", tonic_hz=tonic_hz, raga_id="yaman", tuning_mode="raga_aware",
            next_swara="D", is_ascending=False
        )

        assert p_asc.final_frequency > p_desc.final_frequency
        assert p_asc.context_cents_offset > p_desc.context_cents_offset

    def test_cadence_resolution_stability(self):
        tonic_hz = 200.0
        # Cadential event resets context offset to 0.0
        pitch = shruti_mapper.map_pitch(
            "S", tonic_hz=tonic_hz, raga_id="yaman", tuning_mode="raga_aware",
            is_cadence=True
        )
        assert pitch.context_cents_offset == 0.0
        assert pitch.final_frequency == pytest.approx(tonic_hz, rel=1e-5)


# ============================================================================
# 4. Expression Controller & Phase Continuity Tests
# ============================================================================

class TestExpressionController:
    """Verifies continuous frequency profiles, phase continuity, and ornamentation."""

    def test_meend_frequency_profile(self):
        p1 = ShrutiPitch(swara="G", octave=0, base_frequency=250.0, final_frequency=250.0)
        p2 = ShrutiPitch(swara="P", octave=0, base_frequency=300.0, final_frequency=300.0)
        freqs = expression_controller.generate_frequency_profile(
            current_pitch=p1, next_pitch=p2, num_samples=2205, sample_rate=22050, ornament="meend"
        )

        assert len(freqs) == 2205
        assert freqs[0] == pytest.approx(250.0, abs=1.0)
        assert freqs[-1] == pytest.approx(300.0, abs=1.0)
        assert np.all(freqs >= 249.0)
        assert np.all(freqs <= 301.0)
        # Monotonically non-decreasing for ascending glide
        assert np.all(np.diff(freqs) >= -1e-6)

    def test_kan_grace_prefix_profile(self):
        p = ShrutiPitch(swara="R", octave=0, base_frequency=225.0, final_frequency=225.0)
        freqs = expression_controller.generate_frequency_profile(
            current_pitch=p, num_samples=2205, sample_rate=22050, ornament="kan"
        )

        # Starts higher on grace prefix and smoothly drops to base frequency
        assert freqs[0] > 225.0
        assert freqs[-1] == pytest.approx(225.0, abs=1.0)

    def test_andolan_oscillation_profile(self):
        p = ShrutiPitch(swara="d", octave=0, base_frequency=180.0, final_frequency=180.0)
        freqs = expression_controller.generate_frequency_profile(
            current_pitch=p, num_samples=4410, sample_rate=22050, ornament="andolan"
        )

        assert np.max(freqs) > 180.0
        assert np.min(freqs) < 180.0
        assert np.mean(freqs) == pytest.approx(180.0, abs=1.5)

    def test_gamak_oscillation_profile(self):
        p = ShrutiPitch(swara="D", octave=0, base_frequency=200.0, final_frequency=200.0)
        freqs = expression_controller.generate_frequency_profile(
            current_pitch=p, num_samples=4410, sample_rate=22050, ornament="gamak"
        )

        assert np.max(freqs) > 200.0
        assert np.min(freqs) < 200.0
        # Gamak oscillation depth is larger than andolan
        assert (np.max(freqs) - np.min(freqs)) > 8.0

    def test_phase_continuity_no_jumps(self):
        freqs = np.linspace(200.0, 300.0, 1000)
        phase, final_p = expression_controller.calculate_continuous_phase(freqs, sample_rate=22050, initial_phase=0.0)

        assert len(phase) == 1000
        # Phase differences must always be positive and bounded by 2*pi*f/fs
        d_phase = np.diff(phase)
        assert np.all(d_phase > 0.0)
        assert np.all(d_phase < 0.2)  # 2*pi*300/22050 ~= 0.085


# ============================================================================
# 5. Timbral Synthesis & Percussion Tests
# ============================================================================

class TestTimbralSynthesizer:
    """Verifies multi-timbral synthesis (flute, bowed, ensemble), Tanpura, and Theka."""

    def test_timbral_profiles_generate_distinct_waveforms(self):
        phase = np.linspace(0.0, 2.0 * np.pi * 10, 2205, endpoint=False)
        w_flute = timbral_synthesizer.synthesize_timbre_waveform(phase, sample_rate=22050, timbre_name="flute")
        w_bowed = timbral_synthesizer.synthesize_timbre_waveform(phase, sample_rate=22050, timbre_name="bowed")
        w_ensemble = timbral_synthesizer.synthesize_timbre_waveform(phase, sample_rate=22050, timbre_name="ensemble")

        assert len(w_flute) == 2205
        assert len(w_bowed) == 2205
        assert len(w_ensemble) == 2205

        # Timbres must produce distinct waveforms
        assert not np.allclose(w_flute, w_bowed)
        assert not np.allclose(w_bowed, w_ensemble)

    def test_tanpura_drone_determinism_and_bounds(self):
        d1 = timbral_synthesizer.synthesize_tanpura_drone(138.59, "yaman", num_samples=5000, sample_rate=22050)
        d2 = timbral_synthesizer.synthesize_tanpura_drone(138.59, "yaman", num_samples=5000, sample_rate=22050)

        assert np.array_equal(d1, d2)
        assert not np.isnan(d1).any()
        assert np.max(np.abs(d1)) <= 1.0

    def test_percussion_pulses_align_with_tala_cycles(self):
        ev1 = SwaraEvent(cycle=1, vibhag=1, matra=1, swara="S", pitch_hz=220.0, duration_matras=4.0)
        ev2 = SwaraEvent(cycle=1, vibhag=2, matra=5, swara="P", pitch_hz=330.0, duration_matras=4.0)
        comp = _create_test_composition(events=[ev1, ev2], duration_seconds=6.0)

        perc = timbral_synthesizer.synthesize_theka_pulses(comp, seconds_per_matra=0.5, num_samples=22050, sample_rate=22050)
        assert len(perc) == 22050
        assert not np.isnan(perc).any()
        # Sam on beat 1 must have peak strike at sample 0
        assert np.max(np.abs(perc[:500])) > 0.3


# ============================================================================
# 6. AudioRenderer Multi-Mode & Determinism Tests
# ============================================================================

class TestAudioRendererModes:
    """Verifies end-to-end rendering with canonical, raga_aware, and all timbres."""

    def test_render_canonical_vs_raga_aware_deterministic(self):
        engine = CompositionEngine()
        comp = engine.compose(CompositionRequest(raga_id="yaman", tala_id="teental", duration_seconds=15, seed=42))

        wav_canon_1 = audio_renderer.render_wav_bytes(comp, tuning_mode="canonical", timbre="ensemble")
        wav_canon_2 = audio_renderer.render_wav_bytes(comp, tuning_mode="canonical", timbre="ensemble")
        assert wav_canon_1 == wav_canon_2

        wav_raga_1 = audio_renderer.render_wav_bytes(comp, tuning_mode="raga_aware", timbre="ensemble")
        wav_raga_2 = audio_renderer.render_wav_bytes(comp, tuning_mode="raga_aware", timbre="ensemble")
        assert wav_raga_1 == wav_raga_2

        # Due to Yaman Just Intonation (G, M, D, N offsets), the audio waveforms differ measurably
        assert wav_canon_1 != wav_raga_1

    def test_render_all_timbral_variants(self):
        engine = CompositionEngine()
        comp = engine.compose(CompositionRequest(raga_id="bhairav", tala_id="rupak", duration_seconds=15, seed=7))

        for timbre in ["flute", "bowed", "ensemble"]:
            samples = audio_renderer.render_composition(comp, tuning_mode="raga_aware", timbre=timbre)
            assert len(samples) > 0
            assert not np.isnan(samples).any()
            assert not np.isinf(samples).any()
            assert np.max(np.abs(samples)) <= 0.95


# ============================================================================
# 7. Property-Based Robustness Testing (200+ Validated SwaraEvent Sequences)
# ============================================================================

class TestPropertyRobustness:
    """Property test executing 200+ randomized SwaraEvent sequences."""

    def test_property_200_randomized_sequences(self):
        random.seed(20261002)
        swara_pool = ["S", "r", "R", "g", "G", "m", "M", "P", "d", "D", "n", "N"]
        ornament_pool = ["straight", "meend", "kan", "andolan", "gamak"]
        raga_pool = ["yaman", "bhairav", "todi", "darbari_kanhada", "malkauns", "bhoopali", "bhairavi", "kafi"]
        tuning_modes = ["canonical", "raga_aware"]
        timbres = ["ensemble", "flute", "bowed"]

        for iteration in range(200):
            raga = random.choice(raga_pool)
            tuning = random.choice(tuning_modes)
            timbre = random.choice(timbres)
            tonic_hz = random.uniform(110.0, 300.0)

            # Build 4-8 note events
            num_events = random.randint(4, 8)
            events: List[SwaraEvent] = []
            for ev_i in range(num_events):
                swara_char = random.choice(swara_pool)
                octave_choice = random.choice([-1, 0, 1])
                ornament_choice = random.choice(ornament_pool)
                oct_suffix = "." if octave_choice == -1 else ("'" if octave_choice == 1 else "")
                swara_sym = f"{swara_char}{oct_suffix}"

                semitone = SEMITONE_OFFSETS.get(swara_char, 0)
                raw_hz = tonic_hz * (2.0 ** ((semitone + 12 * octave_choice) / 12.0))

                events.append(
                    SwaraEvent(
                        cycle=1,
                        vibhag=1,
                        matra=ev_i + 1,
                        swara=swara_sym,
                        octave=octave_choice,
                        pitch_hz=raw_hz,
                        duration_matras=random.choice([0.5, 1.0, 2.0]),
                        ornament=ornament_choice,
                    )
                )

            comp = _create_test_composition(
                events=events,
                raga_id=raga,
                duration_seconds=float(num_events * 0.8),
                tonic_hz=tonic_hz,
            )

            samples = audio_renderer.render_composition(comp, tuning_mode=tuning, timbre=timbre)

            # Invariants
            assert isinstance(samples, np.ndarray), f"Iter {iteration}: Output not numpy array"
            assert len(samples) > 0, f"Iter {iteration}: Empty samples"
            assert not np.isnan(samples).any(), f"Iter {iteration}: Contains NaN"
            assert not np.isinf(samples).any(), f"Iter {iteration}: Contains Inf"
            assert np.max(np.abs(samples)) <= 0.95, f"Iter {iteration}: Peak exceeds safe headroom"
            assert np.min(samples) >= -1.0, f"Iter {iteration}: Clipping below -1.0"
