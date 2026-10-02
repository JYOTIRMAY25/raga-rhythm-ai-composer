"""
TonicEstimator for RagaRhythm AI.

Estimates the fundamental tonic frequency (Sa F0 in Hz) of an Indian classical
music performance from preprocessed audio waveforms using multi-pitch harmonic
summation, spectral drone tracking, and harmonic product spectrum analysis.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy import signal

logger = logging.getLogger(__name__)

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


class TonicEstimationResult(BaseModel):
    """Structured output payload for tonic (Sa) estimation."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tonic_hz: float = Field(..., description="Estimated Sa tonic fundamental frequency in Hz")
    note_name: str = Field(..., description="Nearest standard 12-TET note name (e.g. 'D3', 'C#3')")
    cents_deviation: float = Field(..., description="Deviation in cents from the nearest 12-TET equal temperament note")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score [0.0, 1.0]")
    method: str = Field(default="harmonic_drone_hps", description="Estimation algorithm used")
    diagnostics: Dict[str, Any] = Field(default_factory=dict, description="Detailed diagnostic metrics and candidate peaks")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tonic_hz": round(self.tonic_hz, 2),
            "note_name": self.note_name,
            "cents_deviation": round(self.cents_deviation, 1),
            "confidence": round(self.confidence, 3),
            "method": self.method,
            "diagnostics": self.diagnostics,
        }


def hz_to_note_info(freq_hz: float) -> Tuple[str, float]:
    """
    Converts a frequency in Hz to nearest 12-TET note name (with octave)
    and cents deviation from equal temperament (A4 = 440 Hz).
    """
    if freq_hz <= 0.0 or not np.isfinite(freq_hz):
        return "N/A", 0.0

    midi_float = 69.0 + 12.0 * np.log2(freq_hz / 440.0)
    nearest_midi = int(round(midi_float))
    cents_dev = (midi_float - nearest_midi) * 100.0

    note_idx = nearest_midi % 12
    octave = (nearest_midi // 12) - 1
    note_str = f"{NOTE_NAMES[note_idx]}{octave}"
    return note_str, cents_dev


class TonicEstimator:
    """
    Indian Classical Music Tonic (Sa) Estimator.
    
    Identifies the fundamental Sa frequency by analyzing:
    1. Tanpura drone harmonic series (Sa, Pa/Ma, Sa').
    2. Harmonic Product Spectrum (HPS) and subharmonic-to-harmonic ratio.
    3. Multi-frame spectral stationarity.
    
    Invariants:
    - Deterministic output.
    - Graceful silence and NaN/Inf handling without crashing.
    - Valid Hindustani classical vocal/instrumental search band: 110 Hz - 280 Hz.
    - Zero modification of source audio.
    """

    DEFAULT_MIN_FREQ = 110.0
    DEFAULT_MAX_FREQ = 280.0
    DEFAULT_RESOLUTION_HZ = 0.25
    SILENCE_RMS_THRESHOLD = 1e-4

    def __init__(
        self,
        min_freq_hz: float = DEFAULT_MIN_FREQ,
        max_freq_hz: float = DEFAULT_MAX_FREQ,
        freq_resolution_hz: float = DEFAULT_RESOLUTION_HZ,
        analysis_duration_seconds: float = 60.0,
    ):
        self.min_freq_hz = min_freq_hz
        self.max_freq_hz = max_freq_hz
        self.freq_resolution_hz = freq_resolution_hz
        self.analysis_duration_seconds = analysis_duration_seconds

    def _validate_input(self, waveform: np.ndarray, sample_rate: int) -> None:
        """Validates input waveform dimensions, sample rate, and numerical validity."""
        if not isinstance(waveform, np.ndarray):
            raise ValueError(f"Waveform must be a numpy.ndarray, got {type(waveform)}")
        if waveform.ndim != 1:
            raise ValueError(f"Waveform must be 1-dimensional (mono), got shape {waveform.shape}")
        if sample_rate <= 0:
            raise ValueError(f"Sample rate must be positive, got {sample_rate}")
        if len(waveform) == 0:
            raise ValueError("Input waveform is empty (0 samples)")

    def estimate(
        self,
        waveform: np.ndarray,
        sample_rate: int = 22050,
    ) -> TonicEstimationResult:
        """
        Estimates the fundamental tonic frequency (Sa F0) from the input audio waveform.
        
        Args:
            waveform: 1D float array of audio samples (typically normalized at 22050 Hz).
            sample_rate: Audio sampling rate in Hz.
            
        Returns:
            TonicEstimationResult with estimated frequency, confidence, and note name.
        """
        self._validate_input(waveform, sample_rate)

        # Check for NaN / Inf values
        if not np.all(np.isfinite(waveform)):
            logger.warning("Waveform contains NaN or Inf values. Cleaning non-finite values.")
            clean_wave = np.nan_to_num(waveform, nan=0.0, posinf=0.0, neginf=0.0)
        else:
            clean_wave = waveform

        # Check silence
        rms_energy = float(np.sqrt(np.mean(clean_wave ** 2)))
        peak_amp = float(np.max(np.abs(clean_wave))) if len(clean_wave) > 0 else 0.0

        if rms_energy < self.SILENCE_RMS_THRESHOLD or peak_amp < 1e-6:
            return TonicEstimationResult(
                tonic_hz=0.0,
                note_name="N/A",
                cents_deviation=0.0,
                confidence=0.0,
                method="silence_fallback",
                diagnostics={"status": "silent_audio", "rms": rms_energy, "peak": peak_amp},
            )

        # Select analysis slice (skip initial transients if long enough)
        dur_s = len(clean_wave) / sample_rate
        if dur_s > self.analysis_duration_seconds:
            # Skip first 5 seconds to bypass spoken intro or tuning if available
            start_offset = min(int(5.0 * sample_rate), len(clean_wave) // 4)
            end_offset = min(start_offset + int(self.analysis_duration_seconds * sample_rate), len(clean_wave))
            analysis_segment = clean_wave[start_offset:end_offset]
        else:
            analysis_segment = clean_wave

        # Window settings for Welch PSD: 8192 points at 22050 Hz gives ~2.69 Hz resolution
        nperseg = min(8192, len(analysis_segment))
        if nperseg < 512:
            # For very short signals (<25ms)
            nperseg = len(analysis_segment)
            nfft = 4096
        else:
            nfft = 32768  # Interpolates spectrum for ~0.67 Hz bin density

        freqs, psd = signal.welch(
            analysis_segment,
            fs=sample_rate,
            window="hann",
            nperseg=nperseg,
            noverlap=nperseg // 2 if nperseg > 1 else 0,
            nfft=nfft,
        )

        # Grid of candidate frequencies
        num_candidates = int((self.max_freq_hz - self.min_freq_hz) / self.freq_resolution_hz) + 1
        candidate_freqs = np.linspace(self.min_freq_hz, self.max_freq_hz, num_candidates)
        scores = np.zeros_like(candidate_freqs)
        fundamental_energies = np.zeros_like(candidate_freqs)

        # Harmonic weights: Sa fundamental, 2nd octave, 3rd, 4th, 5th harmonics
        harmonic_weights = [(1, 2.0), (2, 1.4), (3, 1.0), (4, 0.7), (5, 0.5)]

        for i, f_cand in enumerate(candidate_freqs):
            idx_fund = np.argmin(np.abs(freqs - f_cand))
            fund_val = float(psd[idx_fund])
            fundamental_energies[i] = fund_val

            h_sum = 0.0
            for mult, weight in harmonic_weights:
                target_f = mult * f_cand
                if target_f < freqs[-1]:
                    idx_h = np.argmin(np.abs(freqs - target_f))
                    h_sum += weight * float(psd[idx_h])

            # Harmonic Product composite score
            scores[i] = h_sum * (np.sqrt(max(0.0, fund_val)) + 1e-9)

        # Candidate peak selection
        best_idx = int(np.argmax(scores))
        best_f = float(candidate_freqs[best_idx])

        # Identify prominent local peaks
        std_score = float(np.std(scores))
        peak_indices, _ = signal.find_peaks(scores, distance=int(3.0 / self.freq_resolution_hz), prominence=std_score * 0.4)

        if len(peak_indices) > 1:
            sorted_peaks = sorted(peak_indices, key=lambda idx: scores[idx], reverse=True)
            top_peak_f = candidate_freqs[sorted_peaks[0]]
            
            # Check for strong fundamental energy preference
            sorted_by_fund = sorted(peak_indices, key=lambda idx: fundamental_energies[idx], reverse=True)
            top_fund_f = candidate_freqs[sorted_by_fund[0]]

            # If the candidate with the highest raw fundamental energy is a major drone relation
            # (e.g., within 20% score of top harmonic peak), select it to avoid fifth/octave errors
            if scores[sorted_by_fund[0]] > 0.65 * scores[sorted_peaks[0]]:
                best_f = float(top_fund_f)
            else:
                best_f = float(top_peak_f)

        # Octave disambiguation: Check if best_f is in high register (e.g. > 215 Hz)
        # while its lower octave subharmonic (f / 2) has strong spectral presence in the male/standard Sa range
        if best_f > 215.0:
            sub_octave_f = best_f / 2.0
            if sub_octave_f >= self.min_freq_hz:
                idx_sub_fund = np.argmin(np.abs(freqs - sub_octave_f))
                idx_best_fund = np.argmin(np.abs(freqs - best_f))
                # If sub-octave has at least 30% of high-octave energy, prefer lower fundamental octave
                if psd[idx_sub_fund] > 0.30 * psd[idx_best_fund]:
                    best_f = float(sub_octave_f)

        # Compute confidence score
        mean_score = float(np.mean(scores))
        max_score = float(scores[np.argmin(np.abs(candidate_freqs - best_f))])
        
        # Confidence based on peak prominence over spectral noise floor
        if std_score > 1e-9:
            raw_conf = (max_score - mean_score) / (3.5 * std_score)
            confidence = float(np.clip(raw_conf, 0.0, 1.0))
        else:
            confidence = 0.0

        note_name, cents_dev = hz_to_note_info(best_f)

        diagnostics = {
            "search_range_hz": [self.min_freq_hz, self.max_freq_hz],
            "analyzed_duration_seconds": round(len(analysis_segment) / sample_rate, 2),
            "rms_energy": round(rms_energy, 5),
            "peak_prominence": round(float(max_score - mean_score), 6),
            "spectral_bins": len(freqs),
        }

        return TonicEstimationResult(
            tonic_hz=round(best_f, 2),
            note_name=note_name,
            cents_deviation=round(cents_dev, 1),
            confidence=round(confidence, 3),
            method="harmonic_drone_hps",
            diagnostics=diagnostics,
        )
