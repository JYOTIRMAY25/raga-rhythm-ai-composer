"""
PitchExtractor for RagaRhythm AI.

Extracts continuous fundamental frequency (F0) pitch contours, voicing masks,
and confidence values from preprocessed audio using an optimized YIN (de Cheveigné
& Kawahara, 2002) time-domain algorithm with parabolic interpolation and
cumulative mean normalized difference function (CMNDF) analysis.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy import signal

logger = logging.getLogger(__name__)


class PitchExtractionResult(BaseModel):
    """Structured result containing continuous pitch track and voicing decisions."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    timestamps_seconds: np.ndarray = Field(..., description="Timestamp in seconds for each analysis frame")
    frequencies_hz: np.ndarray = Field(..., description="Estimated fundamental frequency in Hz (0.0 for unvoiced)")
    voiced_mask: np.ndarray = Field(..., description="Boolean mask indicating voiced frames (True = voiced)")
    confidence_values: np.ndarray = Field(..., description="Voicing / pitch confidence values [0.0, 1.0]")
    frame_rate: float = Field(default=225.0, description="Analysis frame rate in frames per second (e.g. 225 Hz)")
    hop_length: int = Field(default=98, description="Hop length in samples")
    frame_length: int = Field(default=1024, description="Analysis frame length in samples")
    method: str = Field(default="yin_parabolic", description="Pitch extraction algorithm used")
    diagnostics: Dict[str, Any] = Field(default_factory=dict, description="Summary metrics and extraction statistics")

    @property
    def total_frames(self) -> int:
        return len(self.timestamps_seconds)

    @property
    def voiced_frames(self) -> int:
        return int(np.sum(self.voiced_mask))

    @property
    def voiced_percentage(self) -> float:
        return float(self.voiced_frames / self.total_frames * 100.0) if self.total_frames > 0 else 0.0

    def to_summary_dict(self) -> Dict[str, Any]:
        """Returns JSON-serializable summary metadata."""
        voiced_freqs = self.frequencies_hz[self.voiced_mask]
        return {
            "total_frames": self.total_frames,
            "voiced_frames": self.voiced_frames,
            "voiced_percentage": round(self.voiced_percentage, 2),
            "frame_rate": round(self.frame_rate, 2),
            "mean_f0_hz": round(float(np.mean(voiced_freqs)), 2) if len(voiced_freqs) > 0 else 0.0,
            "min_f0_hz": round(float(np.min(voiced_freqs)), 2) if len(voiced_freqs) > 0 else 0.0,
            "max_f0_hz": round(float(np.max(voiced_freqs)), 2) if len(voiced_freqs) > 0 else 0.0,
            "method": self.method,
            "diagnostics": self.diagnostics,
        }


class PitchExtractor:
    """
    Fast, deterministic Hybrid YIN + Harmonic Spectral Saliency Pitch Extractor
    for Indian Classical Music (Hindustani/Carnatic polyphonic recordings).
    
    Features:
    - Default frame rate: 225 Hz (hop_length=98 at 22050 Hz) matching Saraga annotations.
    - Multi-candidate YIN valley discovery with sub-sample parabolic interpolation.
    - Spectral harmonic saliency scoring: weights true fundamental F0 over subharmonics.
    - Subharmonic / octave-halving suppression against Tanpura drone resonance.
    - Optional estimated tonic prior support (Madhya/Mandra/Taar Saptak weighting).
    - Temporal continuity tracking to prevent spurious octave leaps during meend/vibrato.
    - Safe handling of unvoiced/silent frames, NaN/Inf, and extreme pitch jumps.
    - Zero external ML or unapproved package dependencies.
    """

    DEFAULT_FRAME_LENGTH = 1024
    DEFAULT_HOP_LENGTH = 98  # 22050 / 98 = 225.0 Hz frame rate
    DEFAULT_F_MIN_HZ = 65.0   # C2 (~65.4 Hz)
    DEFAULT_F_MAX_HZ = 600.0  # D5 (~587.3 Hz)
    DEFAULT_THRESHOLD = 0.15
    CANDIDATE_MAX_VAL = 0.50
    SILENCE_RMS_THRESHOLD = 1e-4

    def __init__(
        self,
        frame_length: int = DEFAULT_FRAME_LENGTH,
        hop_length: int = DEFAULT_HOP_LENGTH,
        f_min_hz: float = DEFAULT_F_MIN_HZ,
        f_max_hz: float = DEFAULT_F_MAX_HZ,
        threshold: float = DEFAULT_THRESHOLD,
        median_filter_size: int = 3,
    ):
        self.frame_length = frame_length
        self.hop_length = hop_length
        self.f_min_hz = f_min_hz
        self.f_max_hz = f_max_hz
        self.threshold = threshold
        self.median_filter_size = median_filter_size

    def _validate_input(self, waveform: np.ndarray, sample_rate: int) -> np.ndarray:
        """Validates input array and sanitizes non-finite entries."""
        if not isinstance(waveform, np.ndarray):
            raise ValueError(f"Waveform must be a numpy.ndarray, got {type(waveform)}")
        if waveform.ndim != 1:
            raise ValueError(f"Waveform must be 1-dimensional (mono), got shape {waveform.shape}")
        if sample_rate <= 0:
            raise ValueError(f"Sample rate must be positive, got {sample_rate}")
        if len(waveform) == 0:
            raise ValueError("Input waveform is empty (0 samples)")

        if not np.all(np.isfinite(waveform)):
            logger.warning("Waveform contains NaN or Inf values. Sanitizing to zeros.")
            return np.nan_to_num(waveform, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
        return waveform.astype(np.float32)

    def extract(
        self,
        waveform: np.ndarray,
        sample_rate: int = 22050,
        estimated_tonic_hz: Optional[float] = None,
    ) -> PitchExtractionResult:
        """
        Extracts continuous F0 contour, timestamps, voicing masks, and confidence values.
        
        Args:
            waveform: 1D float array of audio samples (typically normalized at 22050 Hz).
            sample_rate: Audio sampling rate in Hz.
            estimated_tonic_hz: Optional estimated Sa tonic frequency in Hz for modal prior weighting.
            
        Returns:
            PitchExtractionResult containing timestamps, frequencies, voicing mask, and confidence.
        """
        clean_wave = self._validate_input(waveform, sample_rate)

        frame_len = min(self.frame_length, len(clean_wave))
        hop_len = max(1, self.hop_length)
        frame_rate = float(sample_rate / hop_len)

        # Bounds on lag tau in samples
        tau_min = max(2, int(sample_rate / self.f_max_hz))
        tau_max = min(frame_len // 2 - 1, int(sample_rate / self.f_min_hz))
        w_len = frame_len // 2

        if tau_max <= tau_min or w_len <= tau_min:
            # Handle exceptionally short audio clips (< 50 ms)
            num_frames = 1
            timestamps = np.array([0.0], dtype=np.float32)
            frequencies = np.array([0.0], dtype=np.float32)
            voiced_mask = np.array([False], dtype=bool)
            confidences = np.array([0.0], dtype=np.float32)
            return PitchExtractionResult(
                timestamps_seconds=timestamps,
                frequencies_hz=frequencies,
                voiced_mask=voiced_mask,
                confidence_values=confidences,
                frame_rate=frame_rate,
                hop_length=hop_len,
                frame_length=frame_len,
                method="hybrid_yin_harmonic_viterbi",
                diagnostics={"status": "audio_too_short", "samples": len(clean_wave)},
            )

        num_frames = max(1, int(np.floor((len(clean_wave) - frame_len) / hop_len)) + 1)
        timestamps = (np.arange(num_frames) * (hop_len / sample_rate)).astype(np.float32)
        frequencies = np.zeros(num_frames, dtype=np.float32)
        confidences = np.zeros(num_frames, dtype=np.float32)
        voiced_mask = np.zeros(num_frames, dtype=bool)

        # Fast FFT spectral parameters for harmonic saliency
        n_fft = 2048
        freq_bin_scale = n_fft / sample_rate
        window = np.hanning(frame_len).astype(np.float32)

        taus = np.arange(tau_max + 1)
        frame_candidates: List[List[Dict[str, Any]]] = []

        # Step 1: Candidate generation & multi-evidence scoring per frame
        for idx in range(num_frames):
            start = idx * hop_len
            frame = clean_wave[start:start + frame_len]
            if len(frame) < frame_len:
                frame = np.pad(frame, (0, frame_len - len(frame)), mode="constant")

            # Check silence / energy
            rms = float(np.sqrt(np.mean(frame ** 2)))
            if rms < self.SILENCE_RMS_THRESHOLD:
                frame_candidates.append([])
                continue

            x = frame[:w_len]
            x_energy = float(np.sum(x ** 2))
            if x_energy < 1e-8:
                frame_candidates.append([])
                continue

            # Compute shifted energies using cumulative sum for O(1) efficiency
            sq = np.pad(frame ** 2, (1, 0), mode="constant")
            cumsum = np.cumsum(sq)
            shifted_energies = cumsum[taus + w_len] - cumsum[taus]

            # Fast cross-correlation
            corr = signal.correlate(frame[:w_len + tau_max], x, mode="valid")
            corr_len = min(len(corr), tau_max + 1)
            d = x_energy + shifted_energies[:corr_len] - 2.0 * corr[:corr_len]

            # Cumulative Mean Normalized Difference Function (CMNDF)
            d_prime = np.zeros(tau_max + 1, dtype=np.float64)
            d_prime[0] = 1.0
            if len(d) > 1:
                cum_d = np.cumsum(d[1:])
                idx_range = np.arange(1, len(d), dtype=np.float64)
                denom = cum_d / idx_range
                denom[denom == 0.0] = 1e-12
                d_prime[1:len(d)] = d[1:] / denom

            search_range = d_prime[tau_min:tau_max]
            if len(search_range) == 0:
                frame_candidates.append([])
                continue

            # Detect all candidate local minima (valleys) in CMNDF
            padded = np.pad(search_range, (1, 1), mode="edge")
            local_min_mask = (search_range < padded[:-2]) & (search_range < padded[2:])
            min_indices = np.where(local_min_mask)[0] + tau_min

            if len(min_indices) == 0:
                min_indices = np.array([np.argmin(search_range) + tau_min])

            # Select top candidate valleys
            if len(min_indices) > 4:
                min_indices = sorted(min_indices, key=lambda t: d_prime[t])[:4]

            # Compute FFT magnitude spectrum of windowed frame for harmonic verification
            fft_mag = np.abs(np.fft.rfft(frame * window, n=n_fft))
            mag_sum = np.sum(fft_mag) + 1e-12
            max_bin = len(fft_mag) - 1

            candidates: List[Dict[str, Any]] = []
            for tau_c in min_indices:
                val = float(d_prime[tau_c])
                # Parabolic sub-sample lag refinement
                if 0 < tau_c < len(d_prime) - 1:
                    alpha = float(d_prime[tau_c - 1])
                    beta = float(d_prime[tau_c])
                    gamma = float(d_prime[tau_c + 1])
                    denom = 2.0 * (alpha - 2.0 * beta + gamma)
                    delta = (alpha - gamma) / denom if abs(denom) > 1e-9 else 0.0
                    tau_ref = float(tau_c + delta)
                else:
                    tau_ref = float(tau_c)

                cand_f = float(sample_rate / tau_ref) if tau_ref > 0 else 0.0
                if not (self.f_min_hz <= cand_f <= self.f_max_hz):
                    continue

                yin_conf = max(0.0, 1.0 - val)

                # Harmonic spectral saliency: check fundamental + 4 harmonics
                harm_energy = 0.0
                for h in (1, 2, 3, 4, 5):
                    bin_idx = int(round(h * cand_f * freq_bin_scale))
                    if bin_idx <= max_bin:
                        b_start = max(0, bin_idx - 1)
                        b_end = min(max_bin + 1, bin_idx + 2)
                        harm_energy += np.max(fft_mag[b_start:b_end]) / (h ** 0.5)

                harm_saliency = float(harm_energy / mag_sum)

                # Subharmonic / Octave-halving suppression:
                # If cand_f is subharmonic (f0 / 2), the 2nd harmonic (true f0) will vastly dominate f1
                f1_bin = int(round(cand_f * freq_bin_scale))
                f2_bin = int(round(2.0 * cand_f * freq_bin_scale))
                e_f1 = float(np.max(fft_mag[max(0, f1_bin - 1):min(max_bin + 1, f1_bin + 2)])) if f1_bin <= max_bin else 0.0
                e_f2 = float(np.max(fft_mag[max(0, f2_bin - 1):min(max_bin + 1, f2_bin + 2)])) if f2_bin <= max_bin else 0.0

                subharmonic_factor = 1.0
                if e_f2 > 2.0 * (e_f1 + 1e-6) and cand_f < 180.0:
                    if e_f1 < 0.15 * e_f2:
                        subharmonic_factor = 0.08  # Severe penalty for missing fundamental ghost
                    else:
                        subharmonic_factor = 0.35

                # Modal tonic prior weighting (if estimated tonic is available)
                tonic_bonus = 1.0
                if estimated_tonic_hz and estimated_tonic_hz > 50.0:
                    semitones_from_tonic = 12.0 * np.log2(cand_f / estimated_tonic_hz)
                    if -7.5 <= semitones_from_tonic <= 26.0:
                        tonic_bonus = 1.20
                    elif semitones_from_tonic < -8.0:
                        tonic_bonus = 0.40

                composite_score = (yin_conf ** 1.3) * (1.0 + 3.0 * harm_saliency) * subharmonic_factor * tonic_bonus
                candidates.append({
                    "f": cand_f,
                    "yin_conf": yin_conf,
                    "score": composite_score,
                    "val": val,
                    "harm_saliency": harm_saliency,
                })

                # If missing fundamental was detected, add true 2*cand_f candidate
                if e_f2 > 2.5 * (e_f1 + 1e-6) and (self.f_min_hz <= 2.0 * cand_f <= self.f_max_hz):
                    doubled_f = 2.0 * cand_f
                    doubled_score = 0.85 * (1.0 + 3.0 * (e_f2 / mag_sum))
                    candidates.append({
                        "f": doubled_f,
                        "yin_conf": 0.85,
                        "score": doubled_score,
                        "val": val,
                        "harm_saliency": e_f2 / mag_sum,
                    })

            frame_candidates.append(candidates)

        # Step 2: Temporal continuity tracking across frames
        for idx in range(num_frames):
            cands = frame_candidates[idx]
            if not cands:
                continue

            cands.sort(key=lambda c: c["score"], reverse=True)
            best_cand = cands[0]

            # If previous frame was voiced, check for spurious octave leaps
            # Only apply continuity if best_cand is not overwhelming in confidence
            if idx > 0 and voiced_mask[idx - 1] and best_cand["yin_conf"] < 0.85:
                prev_f = frequencies[idx - 1]
                best_cents_jump = abs(1200.0 * np.log2(best_cand["f"] / prev_f))
                if best_cents_jump > 550.0:
                    for alt_cand in cands[1:]:
                        alt_cents_jump = abs(1200.0 * np.log2(alt_cand["f"] / prev_f))
                        if alt_cents_jump < 350.0 and alt_cand["score"] > 0.40 * best_cand["score"]:
                            best_cand = alt_cand
                            break

            # Voicing decision: robust confidence threshold
            if best_cand["yin_conf"] >= 0.55 or best_cand["score"] >= 0.60:
                frequencies[idx] = best_cand["f"]
                confidences[idx] = min(1.0, float(best_cand["yin_conf"]))
                voiced_mask[idx] = True

        # Step 3: Post-processing median filtering on contiguous voiced segments
        if self.median_filter_size >= 3 and np.sum(voiced_mask) > 3:
            voiced_indices = np.where(voiced_mask)[0]
            if len(voiced_indices) >= self.median_filter_size:
                smoothed_f0 = signal.medfilt(frequencies[voiced_indices], kernel_size=self.median_filter_size)
                frequencies[voiced_indices] = smoothed_f0.astype(np.float32)

        diagnostics = {
            "total_samples": len(clean_wave),
            "total_frames": num_frames,
            "f_min_hz": self.f_min_hz,
            "f_max_hz": self.f_max_hz,
            "threshold": self.threshold,
            "estimated_tonic_hz": estimated_tonic_hz,
            "method": "hybrid_yin_harmonic_viterbi",
        }

        return PitchExtractionResult(
            timestamps_seconds=timestamps,
            frequencies_hz=frequencies,
            voiced_mask=voiced_mask,
            confidence_values=confidences,
            frame_rate=frame_rate,
            hop_length=hop_len,
            frame_length=frame_len,
            method="hybrid_yin_harmonic_viterbi",
            diagnostics=diagnostics,
        )

