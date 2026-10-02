"""
Production Audio Renderer and WAV Synthesizer for Indian Classical Compositions.
Renders SymbolicComposition into clean, deterministic, 16-bit PCM WAV audio.
Supports microtonal Shruti intonation mapping, timbral synthesis (flute, bowed, ensemble),
and deterministic phase-continuous expression control.
"""

from __future__ import annotations

import io
import math
import struct
from typing import List, Optional, Tuple
import numpy as np

from backend.app.composition.composition_models import (
    SwaraEvent,
    SymbolicComposition,
)
from backend.app.composition.expression import expression_controller
from backend.app.composition.shruti import ShrutiPitch, shruti_mapper
from backend.app.composition.timbre import timbral_synthesizer


class AudioRenderer:
    """
    Synthesizes symbolic Indian Classical Music compositions into high-quality,
    bounded, click-free 16-bit PCM WAV audio with microtonal and multi-timbral support.
    """

    SAMPLE_RATE: int = 22050
    MAX_DURATION_SECONDS: float = 300.0  # Safety cap (5 minutes max)
    MAX_SAMPLES: int = int(MAX_DURATION_SECONDS * SAMPLE_RATE)

    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate

    def render_composition(
        self,
        comp: SymbolicComposition,
        tuning_mode: str = "canonical",
        timbre: str = "ensemble",
    ) -> np.ndarray:
        """
        Renders a full SymbolicComposition into a 1D float32 numpy array in range [-1.0, 1.0].
        Deterministic: Same composition, tuning_mode, and timbre yield bitwise identical output.
        """
        if not comp.events or comp.duration_seconds <= 0:
            return np.zeros(int(self.sample_rate * 0.5), dtype=np.float32)

        duration_sec = min(comp.duration_seconds, self.MAX_DURATION_SECONDS)
        num_samples = int(duration_sec * self.sample_rate)
        num_samples = min(num_samples, self.MAX_SAMPLES)

        if num_samples <= 0:
            return np.zeros(self.sample_rate, dtype=np.float32)

        seconds_per_matra = 60.0 / max(40, min(240, comp.tempo_bpm))
        tonic_hz = max(40.0, min(1000.0, comp.tonic_hz))

        # 1. Synthesize Melody Layer
        melody = np.zeros(num_samples, dtype=np.float64)
        current_matra_offset = 0.0

        for i, ev in enumerate(comp.events):
            event_dur_sec = ev.duration_matras * seconds_per_matra
            start_sample = int(current_matra_offset * self.sample_rate)
            dur_samples = int(event_dur_sec * self.sample_rate)

            if start_sample >= num_samples:
                break
            end_sample = min(num_samples, start_sample + dur_samples)
            actual_samples = end_sample - start_sample

            if actual_samples > 0:
                # Determine melodic context for shruti & glide
                prev_swara = comp.events[i - 1].swara if i > 0 else None
                next_swara = comp.events[i + 1].swara if i + 1 < len(comp.events) else None
                
                # Determine pitch direction
                is_ascending = None
                if next_swara and i + 1 < len(comp.events):
                    next_raw_hz = comp.events[i + 1].pitch_hz
                    is_ascending = (next_raw_hz > ev.pitch_hz)

                is_cadence = (ev.is_sam_landing or ev.matra == 1 or i == len(comp.events) - 1)

                current_pitch = shruti_mapper.map_pitch(
                    swara_symbol=ev.swara,
                    tonic_hz=tonic_hz,
                    raga_id=comp.raga_id,
                    tuning_mode=tuning_mode,
                    prev_swara=prev_swara,
                    next_swara=next_swara,
                    is_ascending=is_ascending,
                    is_cadence=is_cadence,
                    ornament=ev.ornament,
                )

                next_pitch: Optional[ShrutiPitch] = None
                if i + 1 < len(comp.events):
                    next_ev = comp.events[i + 1]
                    next_pitch = shruti_mapper.map_pitch(
                        swara_symbol=next_ev.swara,
                        tonic_hz=tonic_hz,
                        raga_id=comp.raga_id,
                        tuning_mode=tuning_mode,
                    )
                else:
                    # Resolve to Sa
                    next_pitch = shruti_mapper.map_pitch(
                        swara_symbol="S",
                        tonic_hz=tonic_hz,
                        raga_id=comp.raga_id,
                        tuning_mode=tuning_mode,
                    )

                note_samples = self._render_swara_event(
                    current_pitch=current_pitch,
                    next_pitch=next_pitch,
                    num_samples=actual_samples,
                    ornament=ev.ornament,
                    timbre=timbre,
                )
                melody[start_sample:end_sample] += note_samples

            current_matra_offset += ev.duration_matras

        # 2. Synthesize Subtle Tanpura Drone Layer
        drone = self._render_tanpura_drone(
            tonic_hz=tonic_hz,
            raga_id=comp.raga_id,
            num_samples=num_samples,
        )

        # 3. Synthesize Subtle Percussion Pulse (Theka bols & Sam markers)
        percussion = self._render_theka_pulses(
            comp=comp,
            seconds_per_matra=seconds_per_matra,
            num_samples=num_samples,
        )

        # 4. Master Mix (Melody: 0.68, Drone: 0.18, Percussion: 0.14)
        mix = (melody * 0.68) + (drone * 0.18) + (percussion * 0.14)

        # Clean NaN/Inf if any
        mix = np.nan_to_num(mix, nan=0.0, posinf=0.0, neginf=0.0)

        # 5. Master Peak Normalization to -1.0 dBFS (0.89)
        max_peak = np.max(np.abs(mix))
        if max_peak > 1e-6:
            mix = (mix / max_peak) * 0.89
        else:
            mix = np.zeros(num_samples, dtype=np.float32)

        return mix.astype(np.float32)

    def _render_swara_event(
        self,
        current_pitch: ShrutiPitch,
        next_pitch: Optional[ShrutiPitch],
        num_samples: int,
        ornament: Optional[str] = "straight",
        timbre: str = "ensemble",
    ) -> np.ndarray:
        """
        Renders a single discrete swara event with continuous phase and timbral synthesis.
        """
        if num_samples <= 0:
            return np.array([], dtype=np.float64)

        # 1. Continuous Frequency Profile f(t)
        freqs = expression_controller.generate_frequency_profile(
            current_pitch=current_pitch,
            next_pitch=next_pitch,
            num_samples=num_samples,
            sample_rate=self.sample_rate,
            ornament=ornament,
        )

        # 2. Continuous Phase Accumulator phi(t)
        phase, _ = expression_controller.calculate_continuous_phase(
            frequencies=freqs,
            sample_rate=self.sample_rate,
            initial_phase=0.0,
        )

        # 3. Timbral Waveform Synthesis & ADSR Envelope
        return timbral_synthesizer.synthesize_timbre_waveform(
            phase=phase,
            sample_rate=self.sample_rate,
            timbre_name=timbre,
        )

    def _calculate_adsr_envelope(self, num_samples: int) -> np.ndarray:
        """Constructs click-free smooth ADSR amplitude envelope."""
        return expression_controller.calculate_adsr_envelope(
            num_samples=num_samples,
            sample_rate=self.sample_rate,
            attack_ms=15.0,
            release_ms=25.0,
        )

    def _render_tanpura_drone(
        self,
        tonic_hz: float,
        raga_id: str,
        num_samples: int,
    ) -> np.ndarray:
        """Renders Tanpura drone using TimbralSynthesizer."""
        return timbral_synthesizer.synthesize_tanpura_drone(
            tonic_hz=tonic_hz,
            raga_id=raga_id,
            num_samples=num_samples,
            sample_rate=self.sample_rate,
        )

    def _render_theka_pulses(
        self,
        comp: SymbolicComposition,
        seconds_per_matra: float,
        num_samples: int,
    ) -> np.ndarray:
        """Renders theka percussion pulses using TimbralSynthesizer."""
        return timbral_synthesizer.synthesize_theka_pulses(
            comp=comp,
            seconds_per_matra=seconds_per_matra,
            num_samples=num_samples,
            sample_rate=self.sample_rate,
        )

    def encode_wav(self, audio_samples: np.ndarray) -> bytes:
        """
        Encodes a 1D float32 audio numpy array into a valid RIFF 16-bit PCM WAV byte buffer.
        """
        clamped = np.clip(audio_samples, -1.0, 1.0)
        pcm16 = (clamped * 32767.0).astype(np.int16)

        num_channels = 1
        bytes_per_sample = 2
        byte_rate = self.sample_rate * num_channels * bytes_per_sample
        block_align = num_channels * bytes_per_sample
        data_size = len(pcm16) * bytes_per_sample
        chunk_size = 36 + data_size

        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            chunk_size,
            b"WAVE",
            b"fmt ",
            16,  # PCM subchunk size
            1,   # AudioFormat 1 (PCM)
            num_channels,
            self.sample_rate,
            byte_rate,
            block_align,
            16,  # BitsPerSample
            b"data",
            data_size,
        )

        return header + pcm16.tobytes()

    def render_wav_bytes(
        self,
        comp: SymbolicComposition,
        tuning_mode: str = "canonical",
        timbre: str = "ensemble",
    ) -> bytes:
        """Convenience method rendering composition directly to standard WAV bytes."""
        samples = self.render_composition(comp, tuning_mode=tuning_mode, timbre=timbre)
        return self.encode_wav(samples)


audio_renderer = AudioRenderer()
