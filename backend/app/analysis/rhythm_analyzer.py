"""
RhythmAnalyzer for RagaRhythm AI.

Provides low-level rhythmic feature extraction for Hindustani music analysis:
1. Spectral novelty / onset envelope calculation via log-magnitude STFT and rectified spectral flux.
2. Adaptive onset peak detection with configurable refractory spacing.
3. Inter-onset interval (IOI) computation with robust outlier-resistant statistics.
4. Tempo (BPM) estimation via envelope autocorrelation, log-tempo prior weighting, and confidence scoring.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy import signal

logger = logging.getLogger(__name__)


class RhythmFeatures(BaseModel):
    """
    Structured domain model containing low-level rhythmic features and tempo estimation.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    novelty_envelope: np.ndarray = Field(..., description="1D float32 normalized onset novelty envelope")
    novelty_times: np.ndarray = Field(..., description="Timestamp in seconds for each novelty frame")
    onset_times: np.ndarray = Field(..., description="Timestamp in seconds for each detected onset peak")
    onset_frames: np.ndarray = Field(..., description="Frame indices for each detected onset peak")
    ioi_intervals: np.ndarray = Field(..., description="Inter-onset intervals (IOIs) in seconds")
    estimated_bpm: Optional[float] = Field(default=None, description="Estimated tempo in beats per minute (BPM)")
    tempo_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence of tempo estimation [0.0, 1.0]")
    frame_rate: float = Field(default=100.0, description="Novelty analysis frame rate in Hz")
    hop_length: int = Field(default=220, description="STFT hop length in audio samples")
    sample_rate: int = Field(default=22050, description="Audio sampling rate in Hz")
    duration_seconds: float = Field(default=0.0, description="Total duration of analyzed audio in seconds")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="Summary diagnostics and IOI statistics")

    @property
    def total_onsets(self) -> int:
        """Total count of detected onsets."""
        return len(self.onset_times)

    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert result into a JSON-serializable dictionary summary."""
        return {
            "total_onsets": self.total_onsets,
            "estimated_bpm": round(self.estimated_bpm, 2) if self.estimated_bpm is not None else None,
            "tempo_confidence": round(self.tempo_confidence, 4),
            "frame_rate": round(self.frame_rate, 2),
            "duration_seconds": round(self.duration_seconds, 3),
            "statistics": self.statistics,
        }


class RhythmAnalyzer:
    """
    Deterministic DSP-based rhythmic feature extractor and tempo estimator.
    
    Architecture:
        Audio Waveform
            ↓
        Log-Magnitude STFT
            ↓
        Spectral Flux / Novelty Envelope
            ↓
        Adaptive Onset Peak Detection
            ↓
        Inter-Onset Interval (IOI) Statistics
            ↓
        Autocorrelation-based BPM Estimation
    """

    def __init__(
        self,
        sample_rate: int = 22050,
        n_fft: int = 1024,
        hop_length: int = 220,
        min_bpm: float = 30.0,
        max_bpm: float = 360.0,
        onset_delta: float = 0.08,
        min_onset_distance_sec: float = 0.06,
        tempo_prior_mean_bpm: float = 120.0,
        tempo_prior_std_octaves: float = 1.0,
    ):
        """
        Initialize RhythmAnalyzer with configurable DSP parameters.

        Args:
            sample_rate: Audio sampling rate in Hz (default: 22050 Hz).
            n_fft: FFT window size in samples (default: 1024).
            hop_length: Hop length between successive STFT frames (default: 220 -> ~100.2 fps).
            min_bpm: Minimum candidate tempo to evaluate (default: 30.0 BPM).
            max_bpm: Maximum candidate tempo to evaluate (default: 360.0 BPM).
            onset_delta: Threshold delta above local envelope baseline for peak picking.
            min_onset_distance_sec: Minimum refractory period between onsets in seconds (default: 60ms).
            tempo_prior_mean_bpm: Center BPM for log-normal tempo prior weighting (default: 120.0 BPM).
            tempo_prior_std_octaves: Standard deviation in octaves for tempo prior (default: 1.0).
        """
        self.sample_rate = int(sample_rate)
        self.n_fft = int(n_fft)
        self.hop_length = int(hop_length)
        self.min_bpm = float(min_bpm)
        self.max_bpm = float(max_bpm)
        self.onset_delta = float(onset_delta)
        self.min_onset_distance_sec = float(min_onset_distance_sec)
        self.tempo_prior_mean_bpm = float(tempo_prior_mean_bpm)
        self.tempo_prior_std_octaves = float(tempo_prior_std_octaves)

        self.frame_rate = float(self.sample_rate) / float(self.hop_length)

    def compute_spectral_novelty(
        self,
        waveform: np.ndarray,
        sample_rate: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate a time-aligned spectral flux novelty envelope from mono audio.

        Args:
            waveform: 1D floating-point audio waveform.
            sample_rate: Audio sampling rate (defaults to self.sample_rate).

        Returns:
            Tuple of (novelty_envelope, novelty_times):
                - novelty_envelope: 1D float32 normalized novelty curve [0.0, 1.0].
                - novelty_times: 1D float64 timestamps in seconds for each frame.
        """
        sr = sample_rate or self.sample_rate

        # Guard: empty, non-finite, or silent audio
        if waveform is None or len(waveform) == 0:
            return np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.float64)

        clean_wav = np.nan_to_num(waveform, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

        # Handle very short audio (less than one FFT window)
        if len(clean_wav) < self.n_fft:
            pad_amount = self.n_fft - len(clean_wav)
            clean_wav = np.pad(clean_wav, (0, pad_amount), mode="constant")

        # Check for near-silence
        rms = float(np.sqrt(np.mean(clean_wav**2)))
        if rms < 1e-7:
            num_frames = max(1, (len(clean_wav) - self.n_fft) // self.hop_length + 1)
            times = np.arange(num_frames, dtype=np.float64) * (self.hop_length / sr)
            return np.zeros(num_frames, dtype=np.float32), times

        # Compute STFT
        _, _, Zxx = signal.stft(
            clean_wav,
            fs=sr,
            window="hann",
            nperseg=self.n_fft,
            noverlap=self.n_fft - self.hop_length,
            boundary=None,
            padded=False,
        )

        mag = np.abs(Zxx)  # shape: (n_bins, n_frames)
        if mag.shape[1] < 2:
            times = np.arange(mag.shape[1], dtype=np.float64) * (self.hop_length / sr)
            return np.zeros(mag.shape[1], dtype=np.float32), times

        # Log compression: log(1 + gamma * |X|)
        log_mag = np.log1p(10.0 * mag)

        # Positive first-order spectral difference along time (rectified spectral flux)
        diff = np.diff(log_mag, axis=1)
        rectified_diff = np.maximum(0.0, diff)

        # Sum over frequency bins
        raw_novelty = np.sum(rectified_diff, axis=0)

        # Pad first frame so length matches STFT frame count
        raw_novelty = np.pad(raw_novelty, (1, 0), mode="edge")

        # Local adaptive threshold baseline subtraction (detrending)
        # Using a rolling mean / boxcar filter of ~0.25 seconds
        win_size = max(3, int(0.25 * self.frame_rate))
        if win_size % 2 == 0:
            win_size += 1
        
        kernel = np.ones(win_size, dtype=np.float32) / win_size
        local_baseline = signal.convolve(raw_novelty, kernel, mode="same")
        detrended = np.maximum(0.0, raw_novelty - local_baseline)

        # Normalize envelope to [0.0, 1.0]
        max_val = float(np.max(detrended))
        if max_val > 1e-6:
            novelty_env = (detrended / max_val).astype(np.float32)
        else:
            novelty_env = np.zeros_like(detrended, dtype=np.float32)

        novelty_env = np.nan_to_num(novelty_env, nan=0.0, posinf=0.0, neginf=0.0)
        times = np.arange(len(novelty_env), dtype=np.float64) * (self.hop_length / sr)

        return novelty_env, times

    def detect_onsets(
        self,
        novelty_envelope: np.ndarray,
        novelty_times: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Detect onset peaks in the novelty envelope using adaptive local thresholding.

        Args:
            novelty_envelope: 1D float32 normalized novelty curve.
            novelty_times: 1D float64 timestamps for novelty frames.

        Returns:
            Tuple of (onset_times, onset_frames):
                - onset_times: 1D float64 array of onset timestamps in seconds.
                - onset_frames: 1D int array of onset frame indices.
        """
        if len(novelty_envelope) == 0:
            return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.int64)

        # If envelope is purely zero/silent
        if float(np.max(novelty_envelope)) < 1e-4:
            return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.int64)

        # Compute adaptive local threshold: local mean + delta
        win_size = max(5, int(0.3 * self.frame_rate))
        if win_size % 2 == 0:
            win_size += 1
        
        kernel = np.ones(win_size, dtype=np.float32) / win_size
        local_mean = signal.convolve(novelty_envelope, kernel, mode="same")
        threshold = local_mean + self.onset_delta

        # Minimum distance between peaks
        min_dist_frames = max(1, int(self.min_onset_distance_sec * self.frame_rate))

        # Find peaks that exceed the local adaptive threshold
        # We can find candidate peaks above a minimum height
        peaks, properties = signal.find_peaks(
            novelty_envelope,
            distance=min_dist_frames,
            prominence=0.03,
            height=0.05,
        )

        if len(peaks) == 0:
            return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.int64)

        # Filter peaks that exceed the local threshold curve
        valid_mask = novelty_envelope[peaks] >= threshold[peaks]
        valid_peaks = peaks[valid_mask]

        if len(valid_peaks) == 0:
            return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.int64)

        onset_frames = valid_peaks.astype(np.int64)
        onset_times = novelty_times[valid_peaks]

        return onset_times, onset_frames

    def compute_inter_onset_intervals(
        self,
        onset_times: np.ndarray,
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Compute inter-onset intervals (IOIs) and robust summary statistics.

        Args:
            onset_times: 1D array of onset timestamps in seconds.

        Returns:
            Tuple of (iois, statistics_dict):
                - iois: 1D array of positive inter-onset durations in seconds.
                - statistics_dict: dictionary of summary statistics (median, mean, std, iqr, mad).
        """
        if len(onset_times) < 2:
            empty_stats = {
                "count": 0,
                "median_ioi": 0.0,
                "mean_ioi": 0.0,
                "std_ioi": 0.0,
                "iqr_ioi": 0.0,
                "mad_ioi": 0.0,
            }
            return np.zeros(0, dtype=np.float64), empty_stats

        diffs = np.diff(onset_times)
        valid_iois = diffs[diffs > 0.0]

        if len(valid_iois) == 0:
            empty_stats = {
                "count": 0,
                "median_ioi": 0.0,
                "mean_ioi": 0.0,
                "std_ioi": 0.0,
                "iqr_ioi": 0.0,
                "mad_ioi": 0.0,
            }
            return np.zeros(0, dtype=np.float64), empty_stats

        median_val = float(np.median(valid_iois))
        mean_val = float(np.mean(valid_iois))
        std_val = float(np.std(valid_iois))
        
        q75, q25 = np.percentile(valid_iois, [75, 25])
        iqr_val = float(q75 - q25)
        mad_val = float(np.median(np.abs(valid_iois - median_val)))

        stats = {
            "count": len(valid_iois),
            "median_ioi": round(median_val, 5),
            "mean_ioi": round(mean_val, 5),
            "std_ioi": round(std_val, 5),
            "iqr_ioi": round(iqr_val, 5),
            "mad_ioi": round(mad_val, 5),
        }

        return valid_iois, stats

    def estimate_bpm(
        self,
        novelty_envelope: np.ndarray,
        onset_times: np.ndarray,
    ) -> Tuple[Optional[float], float, Dict[str, Any]]:
        """
        Estimate tempo in BPM from envelope autocorrelation with tempo-prior weighting and IOI cross-validation.

        Args:
            novelty_envelope: 1D float32 normalized novelty curve.
            onset_times: 1D float64 onset timestamps.

        Returns:
            Tuple of (estimated_bpm, confidence, diagnostics):
                - estimated_bpm: positive finite float BPM, or None if insufficient rhythmic evidence.
                - confidence: tempo confidence score in [0.0, 1.0].
                - diagnostics: dictionary containing candidate BPMs and peak correlation metrics.
        """
        # Guard: silence, insufficient onsets, or too short envelope
        if (
            len(novelty_envelope) < 10
            or len(onset_times) < 2
            or float(np.max(novelty_envelope)) < 1e-4
        ):
            return None, 0.0, {"reason": "insufficient_onsets_or_silence"}

        # Autocorrelation of novelty envelope
        ac = signal.correlate(novelty_envelope, novelty_envelope, mode="full", method="auto")
        ac = ac[len(novelty_envelope) - 1 :]  # take non-negative lags

        # Calculate lag range corresponding to [min_bpm, max_bpm]
        min_lag = max(1, int(round((60.0 * self.frame_rate) / self.max_bpm)))
        max_lag = min(len(ac) - 1, int(round((60.0 * self.frame_rate) / self.min_bpm)))

        if min_lag >= max_lag or max_lag >= len(ac):
            return None, 0.0, {"reason": "insufficient_frames_for_lag_search"}

        lag_indices = np.arange(min_lag, max_lag + 1)
        lag_bpms = (60.0 * self.frame_rate) / lag_indices

        # Log-normal tempo prior: weights centered at tempo_prior_mean_bpm
        log2_ratio = np.log2(lag_bpms / self.tempo_prior_mean_bpm)
        tempo_prior = np.exp(-0.5 * (log2_ratio / self.tempo_prior_std_octaves) ** 2)

        search_ac = ac[lag_indices].copy()
        
        # Normalize search AC segment
        search_max = float(np.max(search_ac))
        if search_max > 1e-6:
            search_ac /= search_max
        else:
            return None, 0.0, {"reason": "flat_autocorrelation"}

        weighted_ac = search_ac * tempo_prior

        # Compute IOI statistics for candidate cross-validation
        iois, _ = self.compute_inter_onset_intervals(onset_times)
        median_ioi = float(np.median(iois)) if len(iois) > 0 else None

        # Find peaks in raw normalized autocorrelation and weighted autocorrelation
        peaks, _ = signal.find_peaks(
            search_ac,
            distance=max(1, int(0.04 * self.frame_rate)),
            height=0.15,
        )

        if len(peaks) == 0:
            best_idx = int(np.argmax(weighted_ac))
        else:
            # Check candidate peaks
            cand_lags = lag_indices[peaks]
            cand_ac = search_ac[peaks]
            cand_weighted = weighted_ac[peaks]

            best_idx = int(peaks[np.argmax(cand_weighted)])
            
            # If IOI median is available and aligns with a candidate peak, prioritize fundamental pulse
            if median_ioi and median_ioi > 0:
                ioi_lag = median_ioi * self.frame_rate
                for p_idx, (l, p_val) in enumerate(zip(cand_lags, cand_ac)):
                    # Check if candidate lag is close to IOI lag (or half-lag for subharmonics)
                    if abs(l - ioi_lag) <= max(2, int(0.06 * l)) and p_val >= 0.25:
                        best_idx = int(peaks[p_idx])
                        break

        best_lag = float(lag_indices[best_idx])

        # Parabolic interpolation for sub-lag accuracy
        if 0 < best_idx < len(search_ac) - 1:
            alpha = float(search_ac[best_idx - 1])
            beta = float(search_ac[best_idx])
            gamma = float(search_ac[best_idx + 1])
            denom = alpha - 2.0 * beta + gamma
            if abs(denom) > 1e-7:
                delta = 0.5 * (alpha - gamma) / denom
                if abs(delta) < 1.0:
                    best_lag = best_lag + delta

        estimated_bpm = float((60.0 * self.frame_rate) / best_lag)
        estimated_bpm = max(self.min_bpm, min(self.max_bpm, estimated_bpm))

        # Confidence Estimation
        # 1. Peak prominence relative to average AC in search range
        mean_ac = float(np.mean(search_ac))
        peak_ac = float(search_ac[int(np.clip(best_idx, 0, len(search_ac) - 1))])
        ac_contrast = max(0.0, (peak_ac - mean_ac) / (peak_ac + 1e-6))

        # 2. IOI consistency: coefficient of variation of IOIs
        if len(iois) >= 2 and np.mean(iois) > 0:
            ioi_cv = float(np.std(iois) / np.mean(iois))
            ioi_regularity = max(0.0, 1.0 - min(1.0, ioi_cv))
        else:
            ioi_regularity = 0.5

        # Combined confidence bounded in [0.0, 1.0]
        confidence = float(np.clip(0.6 * ac_contrast + 0.4 * ioi_regularity, 0.0, 1.0))

        if confidence < 0.1:
            return None, 0.0, {
                "reason": "low_confidence_periodicity",
                "raw_bpm": estimated_bpm,
                "confidence": confidence,
            }

        diagnostics = {
            "best_lag": round(float(best_lag), 2),
            "peak_contrast": round(ac_contrast, 4),
            "ioi_regularity": round(ioi_regularity, 4),
            "raw_bpm": round(estimated_bpm, 2),
        }

        return round(estimated_bpm, 2), confidence, diagnostics


    def analyze(
        self,
        waveform: np.ndarray,
        sample_rate: Optional[int] = None,
    ) -> RhythmFeatures:
        """
        Execute the full rhythm feature extraction pipeline on an audio waveform.

        Args:
            waveform: 1D mono audio waveform (float).
            sample_rate: Optional sample rate (defaults to self.sample_rate).

        Returns:
            RhythmFeatures object containing novelty curve, onsets, IOIs, and BPM.
        """
        sr = sample_rate or self.sample_rate
        duration = float(len(waveform)) / float(sr) if waveform is not None and len(waveform) > 0 else 0.0

        # 1. Compute spectral novelty
        novelty_env, novelty_times = self.compute_spectral_novelty(waveform, sr)

        # 2. Detect onset peaks
        onset_times, onset_frames = self.detect_onsets(novelty_env, novelty_times)

        # 3. Compute IOIs and statistics
        iois, ioi_stats = self.compute_inter_onset_intervals(onset_times)

        # 4. Estimate BPM
        estimated_bpm, confidence, bpm_diag = self.estimate_bpm(novelty_env, onset_times)

        combined_stats = {
            **ioi_stats,
            "bpm_diagnostics": bpm_diag,
        }

        return RhythmFeatures(
            novelty_envelope=novelty_env,
            novelty_times=novelty_times,
            onset_times=onset_times,
            onset_frames=onset_frames,
            ioi_intervals=iois,
            estimated_bpm=estimated_bpm,
            tempo_confidence=confidence,
            frame_rate=self.frame_rate,
            hop_length=self.hop_length,
            sample_rate=sr,
            duration_seconds=duration,
            statistics=combined_stats,
        )

    def analyze_preprocessed(self, result: Any) -> RhythmFeatures:
        """
        Convenience wrapper to analyze an `AudioPreprocessingResult` instance.

        Args:
            result: AudioPreprocessingResult instance.

        Returns:
            RhythmFeatures object.
        """
        return self.analyze(result.waveform, result.sample_rate)
