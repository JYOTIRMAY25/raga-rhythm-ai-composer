"""
Timbral Synthesizer for Indian Classical Melody, Tanpura Drone, and Tala Percussion.
Provides bounded additive and FM synthesis profiles for flute, bowed strings, and ensemble timbres.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple
import numpy as np

from backend.app.composition.composition_models import SymbolicComposition
from backend.app.composition.expression import expression_controller


class TimbreProfile:
    """Encapsulates harmonic weight distribution and envelope configuration for an instrument."""

    def __init__(
        self,
        name: str,
        harmonics: List[float],
        attack_ms: float = 15.0,
        release_ms: float = 25.0,
        brightness: float = 1.0,
    ):
        self.name = name
        self.harmonics = harmonics
        self.attack_ms = attack_ms
        self.release_ms = release_ms
        self.brightness = brightness


TIMBRE_PROFILES: Dict[str, TimbreProfile] = {
    # 1. Ensemble (Default - classical harmonic blend)
    "ensemble": TimbreProfile(
        name="ensemble",
        harmonics=[0.62, 0.22, 0.10, 0.04, 0.02],
        attack_ms=15.0,
        release_ms=25.0,
        brightness=1.0,
    ),
    # 2. Flute / Bansuri (Dominant fundamental, soft odd harmonics, gentle breath-like envelope)
    "flute": TimbreProfile(
        name="flute",
        harmonics=[0.78, 0.06, 0.12, 0.01, 0.03],
        attack_ms=22.0,
        release_ms=35.0,
        brightness=0.85,
    ),
    # 3. Bowed / Sarangi / Violin (Rich full harmonic spectrum with clear articulation)
    "bowed": TimbreProfile(
        name="bowed",
        harmonics=[0.48, 0.25, 0.14, 0.07, 0.04, 0.02],
        attack_ms=10.0,
        release_ms=28.0,
        brightness=1.15,
    ),
}


class TimbralSynthesizer:
    """
    Renders continuous audio waveforms using specified timbral profiles,
    rich Tanpura drones, and Tala metric pulses.
    """

    @classmethod
    def get_timbre_profile(cls, timbre_name: Optional[str] = "ensemble") -> TimbreProfile:
        clean = (timbre_name or "ensemble").lower().strip()
        return TIMBRE_PROFILES.get(clean, TIMBRE_PROFILES["ensemble"])

    @classmethod
    def synthesize_timbre_waveform(
        cls,
        phase: np.ndarray,
        sample_rate: int,
        timbre_name: str = "ensemble",
        attack_ms: Optional[float] = None,
        release_ms: Optional[float] = None,
    ) -> np.ndarray:
        """
        Synthesizes a multi-harmonic waveform using continuous phase accumulator.
        Applies raised-cosine ADSR envelope without clicks.
        """
        num_samples = len(phase)
        if num_samples <= 0:
            return np.array([], dtype=np.float64)

        profile = cls.get_timbre_profile(timbre_name)
        waveform = np.zeros(num_samples, dtype=np.float64)

        for h_idx, h_weight in enumerate(profile.harmonics, start=1):
            waveform += (h_weight * profile.brightness) * np.sin(float(h_idx) * phase)

        att = attack_ms if attack_ms is not None else profile.attack_ms
        rel = release_ms if release_ms is not None else profile.release_ms
        envelope = expression_controller.calculate_adsr_envelope(
            num_samples=num_samples,
            sample_rate=sample_rate,
            attack_ms=att,
            release_ms=rel,
        )

        return waveform * envelope

    @classmethod
    def synthesize_tanpura_drone(
        cls,
        tonic_hz: float,
        raga_id: str,
        num_samples: int,
        sample_rate: int,
    ) -> np.ndarray:
        """
        Renders an authentic, continuous, deterministic Tanpura drone background:
        Anchors: Pa (1.5x) or Ma (1.333x), Middle Sa (1.0x), Middle Sa (1.002x shimmer), Low Sa (0.5x).
        """
        if num_samples <= 0:
            return np.zeros(0, dtype=np.float64)

        t = np.linspace(0.0, num_samples / float(sample_rate), num_samples, endpoint=False)
        drone = np.zeros(num_samples, dtype=np.float64)

        clean_raga = raga_id.lower().replace("-", "_")
        is_malkauns_family = clean_raga in {"malkauns", "chandrakauns", "bageshri"}
        fifth_hz = tonic_hz * (4.0 / 3.0) if is_malkauns_family else tonic_hz * 1.5

        strings = [
            (fifth_hz, 0.28, [1.0, 0.4, 0.15, 0.05]),         # Pa / Ma anchor
            (tonic_hz, 0.25, [1.0, 0.5, 0.2, 0.08]),          # Jodi Sa 1
            (tonic_hz * 1.002, 0.25, [1.0, 0.5, 0.2, 0.08]),    # Jodi Sa 2 (slight detune for shimmer)
            (tonic_hz * 0.5, 0.22, [1.0, 0.6, 0.3, 0.1]),      # Kharaj Sa (low octave)
        ]

        for base_freq, weight, harmonics in strings:
            string_sig = np.zeros(num_samples, dtype=np.float64)
            for h_idx, h_weight in enumerate(harmonics, start=1):
                h_freq = base_freq * h_idx
                if h_freq < sample_rate / 2.0:
                    string_sig += h_weight * np.sin(2.0 * np.pi * h_freq * t)
            drone += weight * string_sig

        # Deterministic breathing LFO (0.25 Hz)
        slow_lfo = 0.85 + 0.15 * np.sin(2.0 * np.pi * 0.25 * t)
        drone_out = drone * 0.65 * slow_lfo
        return np.clip(drone_out, -1.0, 1.0)

    @classmethod
    def synthesize_theka_pulses(
        cls,
        comp: SymbolicComposition,
        seconds_per_matra: float,
        num_samples: int,
        sample_rate: int,
    ) -> np.ndarray:
        """
        Synthesizes percussive theka strokes aligned with Tala cycles and matra divisions.
        """
        perc = np.zeros(num_samples, dtype=np.float64)
        matras_per_cycle = max(1, comp.matras)
        total_matras = comp.total_matras

        for m_idx in range(total_matras):
            t_sec = m_idx * seconds_per_matra
            start_s = int(t_sec * sample_rate)
            if start_s >= num_samples:
                break

            beat_in_cycle = (m_idx % matras_per_cycle) + 1
            is_sam = (beat_in_cycle == 1)

            pulse_len = int(0.06 * sample_rate)  # 60ms decay stroke
            end_s = min(num_samples, start_s + pulse_len)
            p_samples = end_s - start_s

            if p_samples > 0:
                p_t = np.linspace(0.0, p_samples / float(sample_rate), p_samples, endpoint=False)
                decay = np.exp(-p_t * 60.0)

                if is_sam:
                    # Resonant 'Dha' Sam stroke
                    stroke = np.sin(2.0 * np.pi * 75.0 * p_t) * decay * 0.7
                elif beat_in_cycle in {5, 9, 13}:
                    # Moderate Tali stroke
                    stroke = np.sin(2.0 * np.pi * 140.0 * p_t) * decay * 0.4
                else:
                    # Soft Khali / stroke
                    stroke = np.sin(2.0 * np.pi * 220.0 * p_t) * decay * 0.2

                perc[start_s:end_s] += stroke

        return perc


timbral_synthesizer = TimbralSynthesizer()
