"""
AudioPreprocessor for RagaRhythm AI.

Transforms raw input audio files (MP3, WAV, FLAC, OGG) into standardized,
mono, 22050 Hz normalized floating-point waveforms suitable for downstream
DSP and machine learning analysis.
"""

from __future__ import annotations

import logging
import os
from math import gcd
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# Check if soundfile is available for full MP3/FLAC/OGG decoding
try:
    import soundfile as sf  # type: ignore
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False

# Scipy is available for WAV decoding and high-quality resampling
try:
    from scipy.io import wavfile  # type: ignore
    from scipy import signal  # type: ignore
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


class AudioPreprocessingError(Exception):
    """Base exception for audio preprocessing failures."""
    pass


class AudioTooLongError(AudioPreprocessingError):
    """Raised when audio exceeds the maximum allowed analysis duration."""
    pass


class InvalidAudioError(AudioPreprocessingError):
    """Raised when audio file is corrupt, empty, or unparseable."""
    pass


class AudioPreprocessingResult(BaseModel):
    """Structured result and metadata from audio preprocessing."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    waveform: np.ndarray = Field(..., description="1D float32 normalized mono waveform at 22050 Hz")
    sample_rate: int = Field(default=22050, description="Sampling rate in Hz (always 22050)")
    duration_seconds: float = Field(..., description="Duration of processed audio in seconds")
    number_of_samples: int = Field(..., description="Total count of audio samples")
    channels_original: int = Field(..., description="Channel count of source file before mono conversion")
    peak_amplitude: float = Field(..., description="Maximum absolute amplitude after normalization [0.0, 1.0]")
    rms: float = Field(..., description="Root Mean Square energy of the normalized waveform")
    is_silent: bool = Field(default=False, description="True if audio energy is below silence threshold")
    file_path: str = Field(..., description="Source path of the audio file")

    def to_metadata_dict(self) -> Dict[str, Any]:
        """Returns JSON-serializable summary metadata."""
        return {
            "file_path": self.file_path,
            "sample_rate": self.sample_rate,
            "duration_seconds": round(self.duration_seconds, 3),
            "number_of_samples": self.number_of_samples,
            "channels_original": self.channels_original,
            "peak_amplitude": round(float(self.peak_amplitude), 4),
            "rms": round(float(self.rms), 4),
            "is_silent": self.is_silent,
        }


class AudioPreprocessor:
    """
    Standardized audio preprocessor for Indian classical music analysis.
    
    Invariants:
    - Target sample rate: 22050 Hz
    - Channels: 1 (Mono)
    - Data type: np.float32 normalized to [-1.0, 1.0]
    - Maximum analysis duration: 600.0 seconds (10 minutes)
    - Silence preservation (does not amplify silence/noise)
    - Deterministic output across repeated runs
    - Read-only on source files
    """

    TARGET_SAMPLE_RATE: int = 22050
    MAX_DURATION_SECONDS: float = 600.0  # 10 minutes maximum
    SILENCE_THRESHOLD_RMS: float = 1e-4

    def __init__(
        self,
        target_sample_rate: int = TARGET_SAMPLE_RATE,
        max_duration_seconds: float = MAX_DURATION_SECONDS,
        normalize_peaks: bool = True,
    ):
        self.target_sample_rate = target_sample_rate
        self.max_duration_seconds = max_duration_seconds
        self.normalize_peaks = normalize_peaks

    def validate_file(self, file_path: Union[str, Path]) -> Path:
        """Validates that audio file exists, is non-empty, and accessible."""
        p = Path(file_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Audio file not found: {p}")
        if not p.is_file():
            raise InvalidAudioError(f"Path is not a regular file: {p}")
        if p.stat().st_size == 0:
            raise InvalidAudioError(f"Audio file is empty (0 bytes): {p}")
        return p

    def decode_audio(self, path: Path) -> Tuple[np.ndarray, int, int]:
        """
        Decodes audio into (waveform_array, original_sample_rate, original_channels).
        Supports MP3, WAV, FLAC, OGG via soundfile, with fallback to scipy.io.wavfile for WAV.
        """
        # Primary: soundfile (supports MP3, WAV, FLAC, OGG)
        if HAS_SOUNDFILE:
            try:
                # First check file info without reading entire large file if possible
                info = sf.info(str(path))
                if info.duration > self.max_duration_seconds:
                    raise AudioTooLongError(
                        f"Audio duration ({info.duration:.1f}s) exceeds maximum allowed limit "
                        f"({self.max_duration_seconds:.1f}s)."
                    )
                
                data, sr = sf.read(str(path), dtype="float32", always_2d=True)
                channels = data.shape[1]
                return data, sr, channels
            except AudioTooLongError:
                raise
            except Exception as e:
                # If soundfile fails, try fallback or raise InvalidAudioError
                if not HAS_SCIPY or path.suffix.lower() not in [".wav", ".wave"]:
                    raise InvalidAudioError(f"Could not decode audio file {path.name}: {e}") from e

        # Fallback for WAV using scipy.io.wavfile if soundfile is not available
        if HAS_SCIPY and path.suffix.lower() in [".wav", ".wave"]:
            try:
                sr, data = wavfile.read(str(path))
                if data.dtype == np.int16:
                    data = data.astype(np.float32) / 32768.0
                elif data.dtype == np.int32:
                    data = data.astype(np.float32) / 2147483648.0
                elif data.dtype == np.uint8:
                    data = (data.astype(np.float32) - 128.0) / 128.0
                else:
                    data = data.astype(np.float32)

                if data.ndim == 1:
                    data = data[:, np.newaxis]
                channels = data.shape[1]
                duration = len(data) / float(sr)
                if duration > self.max_duration_seconds:
                    raise AudioTooLongError(
                        f"Audio duration ({duration:.1f}s) exceeds maximum limit "
                        f"({self.max_duration_seconds:.1f}s)."
                    )
                return data, sr, channels
            except AudioTooLongError:
                raise
            except Exception as e:
                raise InvalidAudioError(f"Failed to read WAV file {path.name}: {e}") from e

        raise InvalidAudioError(
            f"No compatible audio decoder available for {path.name}. "
            "Please ensure 'soundfile' is installed to decode MP3/FLAC/OGG files."
        )

    def to_mono(self, waveform: np.ndarray) -> np.ndarray:
        """Converts multi-channel audio (shape: [N, C] or [N]) to 1D mono (shape: [N])."""
        if waveform.ndim == 1:
            return waveform.astype(np.float32)
        if waveform.ndim == 2:
            if waveform.shape[1] == 1:
                return waveform[:, 0].astype(np.float32)
            # Downmix by averaging channels
            return np.mean(waveform, axis=1, dtype=np.float32)
        raise InvalidAudioError(f"Unsupported audio array dimension: {waveform.ndim}")

    def resample(self, waveform: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """
        High-quality, deterministic polyphase resampling using scipy.signal.resample_poly.
        """
        if orig_sr == target_sr:
            return waveform.astype(np.float32)

        if not HAS_SCIPY:
            # Simple linear interpolation fallback if scipy is missing
            old_len = len(waveform)
            new_len = int(round(old_len * target_sr / orig_sr))
            resampled = np.interp(
                np.linspace(0, old_len, new_len, endpoint=False),
                np.arange(old_len),
                waveform
            ).astype(np.float32)
            return resampled

        # Compute reduced rational ratio (up / down)
        g = gcd(orig_sr, target_sr)
        up = target_sr // g
        down = orig_sr // g

        # Use polyphase filtering for optimal audio fidelity and zero phase distortion
        resampled = signal.resample_poly(waveform, up, down).astype(np.float32)
        return resampled

    def normalize(self, waveform: np.ndarray) -> Tuple[np.ndarray, float, float, bool]:
        """
        Peak-normalizes waveform safely without amplifying silence.
        Returns (normalized_waveform, peak_amplitude, rms, is_silent).
        """
        if len(waveform) == 0:
            return waveform, 0.0, 0.0, True

        peak = float(np.max(np.abs(waveform)))
        rms = float(np.sqrt(np.mean(waveform ** 2)))
        is_silent = rms < self.SILENCE_THRESHOLD_RMS or peak < 1e-6

        if is_silent or not self.normalize_peaks:
            return waveform.astype(np.float32), peak, rms, is_silent

        # Normalize peak to 0.99 (leaving -0.1 dB headroom against clipping)
        normalized = (waveform / peak) * 0.99
        new_peak = float(np.max(np.abs(normalized)))
        new_rms = float(np.sqrt(np.mean(normalized ** 2)))

        return normalized.astype(np.float32), new_peak, new_rms, False

    def process(
        self,
        file_path: Union[str, Path],
        max_duration_seconds: Optional[float] = None,
    ) -> AudioPreprocessingResult:
        """
        Full end-to-end audio validation and preprocessing pipeline.
        
        Steps:
        1. Validate path & size
        2. Decode stream (enforcing max duration limit)
        3. Convert to mono
        4. Resample to 22050 Hz
        5. Normalize amplitude safely
        6. Compute metrics and return structured AudioPreprocessingResult
        """
        effective_max_dur = max_duration_seconds or self.max_duration_seconds
        valid_path = self.validate_file(file_path)

        # Decode
        raw_data, orig_sr, orig_channels = self.decode_audio(valid_path)

        # Check decoded duration
        duration_raw = len(raw_data) / float(orig_sr)
        if duration_raw > effective_max_dur:
            raise AudioTooLongError(
                f"Audio file duration ({duration_raw:.2f}s) exceeds maximum allowed duration ({effective_max_dur:.2f}s)"
            )

        # Convert to mono
        mono_data = self.to_mono(raw_data)

        # Resample to 22050 Hz
        resampled_data = self.resample(mono_data, orig_sr, self.target_sample_rate)

        # Normalize
        norm_data, peak, rms, is_silent = self.normalize(resampled_data)

        num_samples = len(norm_data)
        final_duration = num_samples / float(self.target_sample_rate)

        return AudioPreprocessingResult(
            waveform=norm_data,
            sample_rate=self.target_sample_rate,
            duration_seconds=final_duration,
            number_of_samples=num_samples,
            channels_original=orig_channels,
            peak_amplitude=peak,
            rms=rms,
            is_silent=is_silent,
            file_path=str(valid_path),
        )
