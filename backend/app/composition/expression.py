"""
Expression Controller for Indian Classical Melodic Articulation.
Generates bounded, click-free continuous frequency and phase trajectories
for all classical ornamentation styles (straight, meend, kan, andolan, gamak).
"""

from __future__ import annotations

import math
from typing import Optional, Tuple
import numpy as np

from backend.app.composition.shruti import ShrutiPitch


class ExpressionController:
    """
    Synthesizes smooth, continuous instantaneous frequency curves f(t) and
    continuous phase accumulators phi(t) for symbolic note events.
    """

    MIN_FREQ_HZ: float = 20.0
    MAX_FREQ_HZ: float = 3000.0

    @classmethod
    def generate_frequency_profile(
        cls,
        current_pitch: ShrutiPitch,
        num_samples: int,
        sample_rate: int,
        next_pitch: Optional[ShrutiPitch] = None,
        ornament: Optional[str] = "straight",
    ) -> np.ndarray:
        """
        Builds a 1D float64 instantaneous frequency profile array of length `num_samples`.
        Guarantees deterministic, bounded, NaN/Inf-free output.
        """
        if num_samples <= 0:
            return np.array([], dtype=np.float64)

        base_f0 = float(np.clip(current_pitch.final_frequency, cls.MIN_FREQ_HZ, cls.MAX_FREQ_HZ))
        dur_sec = max(1e-5, num_samples / sample_rate)
        t = np.linspace(0.0, dur_sec, num_samples, endpoint=False)
        clean_ornament = (ornament or "straight").lower().strip()

        if clean_ornament == "meend" and next_pitch is not None and next_pitch.final_frequency > 0:
            target_f = float(np.clip(next_pitch.final_frequency, cls.MIN_FREQ_HZ, cls.MAX_FREQ_HZ))
            glide_start = 0.40  # Glide initiates at 40% into note duration
            phase_norm = np.clip((t / dur_sec - glide_start) / (1.0 - glide_start), 0.0, 1.0)
            # Smooth cosine S-curve transition
            glide_curve = 0.5 * (1.0 - np.cos(np.pi * phase_norm))
            freqs = base_f0 + (target_f - base_f0) * glide_curve

        elif clean_ornament == "kan":
            # Grace note prefix: transient start +2 semitones (1.1224x) for first 15%
            grace_f = base_f0 * (2.0 ** (2.0 / 12.0))
            frac = np.clip(t / (0.15 * dur_sec + 1e-6), 0.0, 1.0)
            # Smoothly descends from grace note to target base frequency
            grace_curve = grace_f + (base_f0 - grace_f) * (0.5 * (1.0 - np.cos(np.pi * frac)))
            freqs = np.where(t < 0.15 * dur_sec, grace_curve, base_f0)

        elif clean_ornament == "andolan":
            # Gentle slow microtonal oscillation (~3.5 Hz, ~35 cents / 2.0% amplitude)
            mod_rate = 3.5
            mod_depth = 0.02
            freqs = base_f0 * (1.0 + mod_depth * np.sin(2.0 * np.pi * mod_rate * t))

        elif clean_ornament == "gamak":
            # Rapid vigorous oscillation (~6.0 Hz, ~60 cents / 3.5% amplitude)
            mod_rate = 6.0
            mod_depth = 0.035
            freqs = base_f0 * (1.0 + mod_depth * np.sin(2.0 * np.pi * mod_rate * t))

        else:
            # Steady canonical tone
            freqs = np.full(num_samples, base_f0, dtype=np.float64)

        # Sanitize and strictly bound frequencies
        freqs = np.nan_to_num(freqs, nan=base_f0, posinf=cls.MAX_FREQ_HZ, neginf=cls.MIN_FREQ_HZ)
        return np.clip(freqs, cls.MIN_FREQ_HZ, cls.MAX_FREQ_HZ)

    @classmethod
    def calculate_continuous_phase(
        cls,
        frequencies: np.ndarray,
        sample_rate: int,
        initial_phase: float = 0.0,
    ) -> Tuple[np.ndarray, float]:
        """
        Integrates instantaneous frequencies into continuous phase trajectory:
        phi[n] = initial_phase + sum_{k=0}^{n} (2 * pi * f[k] / sample_rate)
        Returns (phase_array, final_phase_mod_2pi).
        """
        if len(frequencies) == 0:
            return np.array([], dtype=np.float64), initial_phase

        delta_phase = 2.0 * np.pi * frequencies / float(sample_rate)
        phase_accum = initial_phase + np.cumsum(delta_phase)
        final_phase = float(phase_accum[-1] % (2.0 * np.pi))

        return phase_accum, final_phase

    @classmethod
    def calculate_adsr_envelope(
        cls,
        num_samples: int,
        sample_rate: int,
        attack_ms: float = 15.0,
        release_ms: float = 25.0,
    ) -> np.ndarray:
        """
        Generates a click-free raised-cosine ADSR amplitude envelope.
        """
        if num_samples <= 0:
            return np.array([], dtype=np.float64)

        env = np.ones(num_samples, dtype=np.float64)
        attack_len = min(int((attack_ms / 1000.0) * sample_rate), num_samples // 3)
        release_len = min(int((release_ms / 1000.0) * sample_rate), num_samples // 3)

        if attack_len > 0:
            # Half-cosine attack from 0 to 1
            env[:attack_len] = 0.5 * (1.0 - np.cos(np.pi * np.linspace(0.0, 1.0, attack_len)))

        if release_len > 0:
            # Half-cosine release from 1 to 0
            env[-release_len:] = 0.5 * (1.0 + np.cos(np.pi * np.linspace(0.0, 1.0, release_len)))

        return env


expression_controller = ExpressionController()
