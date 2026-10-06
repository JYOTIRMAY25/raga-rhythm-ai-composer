"""
AnalysisPipeline for RagaRhythm AI.

Single unified orchestrator executing the frozen multi-stage musicological DSP pipeline:
Audio
  ↓
AudioPreprocessor
  ↓
TonicEstimator
  ↓
PitchExtractor
  ↓
TonicResolver
  ↓
SwaraAnalyzer
  ├── RagaDetector + MelodicMotifMatcher
  └── RhythmAnalyzer
        ↓
     BeatTracker
        ↓
     TalaClassifier
  ↓
Unified AnalysisResult Payload

Preserves all underlying module invariants and behaviors using minimal, non-invasive adapters.
"""

from __future__ import annotations

import logging
import math
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.exceptions import JobCancelledException
from .preprocessor import (
    AudioPreprocessor,
    AudioPreprocessingResult,
    AudioPreprocessingError,
    AudioTooLongError,
    InvalidAudioError,
)
from .tonic_estimator import TonicEstimator, TonicEstimationResult, hz_to_note_info
from .pitch_extractor import PitchExtractor, PitchExtractionResult
from .tonic_resolver import TonicResolver, TonicResolutionResult, TonicCandidate
from .swara_analyzer import (
    SwaraAnalyzer,
    SwaraAnalysisResult,
    SwaraSegment,
    SWARA_DEFINITIONS,
)
from .raga_detector import (
    RagaDetector,
    RagaAnalysisResult,
    RagaCandidate,
    RAGA_KNOWLEDGE_BASE,
)
from .motif_matcher import MotifMatchEvidence
from .rhythm_analyzer import RhythmAnalyzer, RhythmFeatures
from .beat_tracker import BeatTracker, BeatGrid
from .tala_classifier import (
    TalaClassifier,
    TalaCandidate as TalaClassifierCandidate,
    TalaClassificationResult,
)
from .tala_knowledge_base import get_tala

logger = logging.getLogger(__name__)


def _sanitize_float(val: Optional[Union[float, int]], default: Optional[float] = None) -> Optional[float]:
    """Sanitizes floats to prevent NaN / Inf serialization in JSON."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


def _clamp_confidence(val: Optional[float], default: float = 0.0) -> float:
    """Clamps confidence values strictly to [0.0, 1.0]."""
    f = _sanitize_float(val, default)
    if f is None:
        return default
    return max(0.0, min(1.0, f))


def _classify_laya(bpm: Optional[float]) -> str:
    """Classifies BPM into Hindustani Laya tempo categories."""
    if bpm is None or bpm <= 0.0:
        return "Unknown"
    if bpm < 65.0:
        return "Vilambit"
    elif bpm <= 150.0:
        return "Madhya"
    else:
        return "Drut"


# ============================================================================
# Compact Domain Result Models for Pipeline Output
# ============================================================================

class PipelineAudioMetadata(BaseModel):
    """Metadata for processed audio file."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    file_path: Optional[str] = None
    filename: Optional[str] = None
    sample_rate: int = 22050
    duration_seconds: float = Field(ge=0.0)
    number_of_samples: int = Field(ge=0)
    channels_original: int = Field(ge=1)
    peak_amplitude: float = Field(ge=0.0, le=1.0)
    rms: float = Field(ge=0.0)
    is_silent: bool = False


class PipelineTonicResult(BaseModel):
    """Resolved tonic (Sa) information."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    frequency_hz: Optional[float] = None
    note_name: Optional[str] = None
    octave: Optional[int] = None
    cents_deviation: Optional[float] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_ambiguous: bool = False
    method: str = "multi_feature_tonic_resolver"
    runner_up_hz: Optional[float] = None


class PipelinePitchSummary(BaseModel):
    """Summary of continuous pitch extraction."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    total_frames: int = Field(ge=0)
    voiced_frames: int = Field(ge=0)
    voiced_percentage: float = Field(ge=0.0, le=100.0)
    frame_rate: float = Field(ge=0.0)
    mean_f0_hz: Optional[float] = None
    min_f0_hz: Optional[float] = None
    max_f0_hz: Optional[float] = None
    method: str = "yin_parabolic"
    downsampled_timestamps: List[float] = Field(default_factory=list)
    downsampled_frequencies: List[float] = Field(default_factory=list)


class PipelineSwaraSummary(BaseModel):
    """Summary of swara mapping and distribution."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    pitch_class_distribution: Dict[str, float] = Field(default_factory=dict)
    active_swaras: List[str] = Field(default_factory=list)
    total_segments: int = Field(ge=0)
    mean_cents_deviation: float = 0.0
    dominant_swaras: List[str] = Field(default_factory=list)
    transitions_top: List[Dict[str, Any]] = Field(default_factory=list)


class PipelineRagaAlternative(BaseModel):
    """Alternative candidate raga."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    raga_id: str
    name: str
    thaat: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    composite_score: float = 0.0


class PipelineMotifMatch(BaseModel):
    """Detected melodic pakad motif match evidence."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    motif: List[str]
    motif_str: str
    match_type: str
    matched_subsequence: List[str]
    similarity_score: float = Field(ge=0.0, le=1.0)
    start_time_seconds: Optional[float] = None
    end_time_seconds: Optional[float] = None


class PipelineRagaResult(BaseModel):
    """Detected Raga result with candidates and theoretical characteristics."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    predicted_raga: Optional[str] = None
    predicted_raga_id: Optional[str] = None
    thaat: Optional[str] = None
    time: Optional[str] = None
    mood: Optional[str] = None
    vadi: Optional[str] = None
    samvadi: Optional[str] = None
    aroha: List[str] = Field(default_factory=list)
    avaroha: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_ambiguous: bool = False
    alternatives: List[PipelineRagaAlternative] = Field(default_factory=list)
    motif_matches: List[PipelineMotifMatch] = Field(default_factory=list)


class PipelineRhythmSummary(BaseModel):
    """Summary of rhythmic onset and tempo extraction."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    estimated_bpm: Optional[float] = None
    laya: str = "Unknown"
    tempo_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    total_onsets: int = Field(ge=0)
    frame_rate: float = 100.0


class PipelineBeatGridSummary(BaseModel):
    """Summary of beat tracker and matra grid alignment."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    beat_count: int = Field(ge=0)
    beat_period: float = Field(ge=0.0)
    bpm: Optional[float] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    selected_hypothesis: str = "1.0x"
    first_beat_time: Optional[float] = None
    sam_timestamps: List[float] = Field(default_factory=list)
    cycle_length: Optional[int] = None


class PipelineTalaCandidate(BaseModel):
    """Candidate Tala evaluation."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tala_id: str
    name: str
    matras: int
    confidence: float = Field(ge=0.0, le=1.0)
    composite_score: float = 0.0


class PipelineTalaResult(BaseModel):
    """Classified Tala result and rhythmic structure."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    predicted_tala: Optional[str] = None
    predicted_tala_id: Optional[str] = None
    matras: Optional[int] = None
    vibhag_structure: Optional[str] = None
    theka: Optional[str] = None
    sam_position: Optional[int] = 1
    khali_positions: List[int] = Field(default_factory=list)
    tali_positions: List[int] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_ambiguous: bool = False
    candidates: List[PipelineTalaCandidate] = Field(default_factory=list)
    tempo_hypothesis: str = "1.0x"


class PipelineWarning(BaseModel):
    """Warning emitted during analysis pipeline execution."""
    stage: str
    code: str
    message: str


class UnifiedAnalysisResult(BaseModel):
    """
    Unified end-to-end analysis payload aggregating all musicological DSP outputs.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    audio_metadata: PipelineAudioMetadata
    tonic: PipelineTonicResult
    pitch: PipelinePitchSummary
    swara: PipelineSwaraSummary
    raga: PipelineRagaResult
    rhythm: PipelineRhythmSummary
    beat_grid: PipelineBeatGridSummary
    tala: PipelineTalaResult
    warnings: List[PipelineWarning] = Field(default_factory=list)
    processing_time_ms: float = Field(ge=0.0)
    stage_timings_ms: Dict[str, float] = Field(default_factory=dict)


# ============================================================================
# Unified Analysis Pipeline
# ============================================================================

class AnalysisPipeline:
    """
    High-level orchestration engine running the complete RagaRhythm analysis suite.
    """

    def __init__(
        self,
        preprocessor: Optional[AudioPreprocessor] = None,
        tonic_estimator: Optional[TonicEstimator] = None,
        tonic_resolver: Optional[TonicResolver] = None,
        pitch_extractor: Optional[PitchExtractor] = None,
        swara_analyzer: Optional[SwaraAnalyzer] = None,
        raga_detector: Optional[RagaDetector] = None,
        rhythm_analyzer: Optional[RhythmAnalyzer] = None,
        beat_tracker: Optional[BeatTracker] = None,
        tala_classifier: Optional[TalaClassifier] = None,
    ) -> None:
        self.preprocessor = preprocessor or AudioPreprocessor()
        self.tonic_estimator = tonic_estimator or TonicEstimator()
        self.tonic_resolver = tonic_resolver or TonicResolver()
        self.pitch_extractor = pitch_extractor or PitchExtractor()
        self.swara_analyzer = swara_analyzer or SwaraAnalyzer()
        self.raga_detector = raga_detector or RagaDetector()
        self.rhythm_analyzer = rhythm_analyzer or RhythmAnalyzer()
        self.beat_tracker = beat_tracker or BeatTracker()
        self.tala_classifier = tala_classifier or TalaClassifier()

    @staticmethod
    def _report_progress(
        callback: Optional[Callable[[int, str], None]],
        progress: int,
        stage: str,
    ) -> None:
        """Safely invokes progress callback without interrupting analysis if it fails."""
        if callback is not None:
            try:
                callback(progress, stage)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    @staticmethod
    def _check_cancellation(cancellation_check: Optional[Callable[[], bool]]) -> None:
        """Checks if cancellation was requested and raises JobCancelledException at safe stage boundaries."""
        if cancellation_check is not None:
            try:
                if cancellation_check():
                    raise JobCancelledException("Analysis cancelled by client request.")
            except JobCancelledException:
                raise
            except Exception as e:
                logger.warning(f"Cancellation check error: {e}")

    def process_file(
        self,
        file_path: Union[str, Path],
        max_downsampled_points: int = 150,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> UnifiedAnalysisResult:
        """
        Executes the unified analysis pipeline on a given audio file path.
        """
        start_total = time.perf_counter()
        stage_timings: Dict[str, float] = {}
        warnings: List[PipelineWarning] = []

        self._check_cancellation(cancellation_check)
        self._report_progress(progress_callback, 5, "Audio preprocessing")

        # --------------------------------------------------------------------
        # Stage 1: Audio Preprocessing
        # --------------------------------------------------------------------
        t0 = time.perf_counter()
        p = Path(file_path).resolve()
        pre_res: AudioPreprocessingResult = self.preprocessor.process(p)
        stage_timings["preprocessing"] = round((time.perf_counter() - t0) * 1000.0, 2)

        return self._process_preprocessed_audio(
            pre_res=pre_res,
            file_name=p.name,
            file_path=str(p),
            start_total=start_total,
            stage_timings=stage_timings,
            warnings=warnings,
            max_downsampled_points=max_downsampled_points,
            progress_callback=progress_callback,
            cancellation_check=cancellation_check,
        )

    def process_waveform(
        self,
        waveform: np.ndarray,
        sample_rate: int = 22050,
        filename: str = "waveform_input.wav",
        max_downsampled_points: int = 150,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> UnifiedAnalysisResult:
        """
        Executes the unified analysis pipeline on an in-memory waveform.
        """
        start_total = time.perf_counter()
        stage_timings: Dict[str, float] = {}
        warnings: List[PipelineWarning] = []

        self._check_cancellation(cancellation_check)
        self._report_progress(progress_callback, 5, "Audio preprocessing")

        t0 = time.perf_counter()
        orig_channels = 1 if waveform.ndim == 1 else waveform.shape[1] if waveform.ndim == 2 else 1
        mono_data = self.preprocessor.to_mono(waveform)
        resampled_data = self.preprocessor.resample(mono_data, sample_rate, self.preprocessor.target_sample_rate)
        norm_data, peak, rms, is_silent = self.preprocessor.normalize(resampled_data)
        num_samples = len(norm_data)
        final_duration = num_samples / float(self.preprocessor.target_sample_rate)

        pre_res = AudioPreprocessingResult(
            waveform=norm_data,
            sample_rate=self.preprocessor.target_sample_rate,
            duration_seconds=final_duration,
            number_of_samples=num_samples,
            channels_original=orig_channels,
            peak_amplitude=peak,
            rms=rms,
            is_silent=is_silent,
            file_path=filename,
        )
        stage_timings["preprocessing"] = round((time.perf_counter() - t0) * 1000.0, 2)

        return self._process_preprocessed_audio(
            pre_res=pre_res,
            file_name=filename,
            file_path=None,
            start_total=start_total,
            stage_timings=stage_timings,
            warnings=warnings,
            max_downsampled_points=max_downsampled_points,
            progress_callback=progress_callback,
            cancellation_check=cancellation_check,
        )

    def _process_preprocessed_audio(
        self,
        pre_res: AudioPreprocessingResult,
        file_name: str,
        file_path: Optional[str],
        start_total: float,
        stage_timings: Dict[str, float],
        warnings: List[PipelineWarning],
        max_downsampled_points: int,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> UnifiedAnalysisResult:
        """Internal worker executing downstream stages after preprocessing."""

        # Audio Metadata payload
        audio_meta = PipelineAudioMetadata(
            file_path=file_path,
            filename=file_name,
            sample_rate=pre_res.sample_rate,
            duration_seconds=round(max(0.0, float(pre_res.duration_seconds)), 3),
            number_of_samples=int(pre_res.number_of_samples),
            channels_original=int(pre_res.channels_original),
            peak_amplitude=_clamp_confidence(pre_res.peak_amplitude, 0.0),
            rms=max(0.0, _sanitize_float(pre_res.rms, 0.0) or 0.0),
            is_silent=bool(pre_res.is_silent),
        )

        if pre_res.is_silent:
            warnings.append(
                PipelineWarning(
                    stage="preprocessing",
                    code="AUDIO_SILENT",
                    message="The provided audio contains near-zero RMS energy and was flagged as silent.",
                )
            )

        if pre_res.duration_seconds < 3.0:
            warnings.append(
                PipelineWarning(
                    stage="preprocessing",
                    code="AUDIO_SHORT",
                    message=f"Audio duration ({pre_res.duration_seconds:.1f}s) is short (<3.0s). Results may have lower statistical confidence.",
                )
            )

        # --------------------------------------------------------------------
        # Stage 2: Tonic Estimation (Sa Baseline)
        # --------------------------------------------------------------------
        self._check_cancellation(cancellation_check)
        self._report_progress(progress_callback, 15, "Tonic estimation")

        t0 = time.perf_counter()
        tonic_est: TonicEstimationResult = self.tonic_estimator.estimate(
            pre_res.waveform,
            sample_rate=pre_res.sample_rate,
        )
        stage_timings["tonic_estimation"] = round((time.perf_counter() - t0) * 1000.0, 2)

        # --------------------------------------------------------------------
        # Stage 3: Continuous Pitch Extraction (YIN)
        # --------------------------------------------------------------------
        self._check_cancellation(cancellation_check)
        self._report_progress(progress_callback, 30, "Pitch extraction")

        t0 = time.perf_counter()
        pitch_res: PitchExtractionResult = self.pitch_extractor.extract(
            pre_res.waveform,
            sample_rate=pre_res.sample_rate,
            estimated_tonic_hz=tonic_est.tonic_hz,
        )
        stage_timings["pitch_extraction"] = round((time.perf_counter() - t0) * 1000.0, 2)

        # --------------------------------------------------------------------
        # Stage 4: Multi-Candidate Tonic Resolution
        # --------------------------------------------------------------------
        self._check_cancellation(cancellation_check)
        self._report_progress(progress_callback, 50, "Tonic resolution")

        t0 = time.perf_counter()
        tonic_res: TonicResolutionResult = self.tonic_resolver.resolve(
            waveform=pre_res.waveform,
            sample_rate=pre_res.sample_rate,
            pitch_result=pitch_res,
            tonic_estimate=tonic_est,
        )
        stage_timings["tonic_resolution"] = round((time.perf_counter() - t0) * 1000.0, 2)

        # Determine effective tonic frequency
        resolved_tonic_hz = _sanitize_float(tonic_res.tonic_hz)
        if resolved_tonic_hz is None or resolved_tonic_hz <= 0.0:
            resolved_tonic_hz = _sanitize_float(tonic_est.tonic_hz, 140.0)

        runner_up_hz = None
        if len(tonic_res.candidates) > 1:
            runner_up_hz = _sanitize_float(tonic_res.candidates[1].frequency_hz)

        tonic_payload = PipelineTonicResult(
            frequency_hz=round(resolved_tonic_hz, 2) if resolved_tonic_hz else None,
            note_name=tonic_res.note_name or tonic_est.note_name or "Unknown",
            octave=tonic_res.selected_tonic.octave if tonic_res.selected_tonic else None,
            cents_deviation=_sanitize_float(tonic_res.selected_tonic.cents_deviation if tonic_res.selected_tonic else 0.0),
            confidence=_clamp_confidence(tonic_res.confidence),
            is_ambiguous=bool(tonic_res.ambiguity_flag),
            method=tonic_res.method,
            runner_up_hz=round(runner_up_hz, 2) if runner_up_hz else None,
        )

        if tonic_res.ambiguity_flag:
            warnings.append(
                PipelineWarning(
                    stage="tonic_resolution",
                    code="TONIC_AMBIGUOUS",
                    message="Tonic resolver detected closely competing harmonic candidates (e.g. Sa vs Pa/Ma).",
                )
            )

        # Downsample pitch contour for compact API payload
        voiced_indices = np.where(pitch_res.voiced_mask)[0]
        downsampled_ts: List[float] = []
        downsampled_f0: List[float] = []
        if len(voiced_indices) > 0:
            step = max(1, len(voiced_indices) // max_downsampled_points)
            sampled_idx = voiced_indices[::step]
            for idx in sampled_idx:
                downsampled_ts.append(round(float(pitch_res.timestamps_seconds[idx]), 3))
                downsampled_f0.append(round(float(pitch_res.frequencies_hz[idx]), 2))

        pitch_summary_dict = pitch_res.to_summary_dict()
        pitch_payload = PipelinePitchSummary(
            total_frames=pitch_res.total_frames,
            voiced_frames=pitch_res.voiced_frames,
            voiced_percentage=round(_clamp_confidence(pitch_res.voiced_percentage / 100.0) * 100.0, 2),
            frame_rate=round(_sanitize_float(pitch_res.frame_rate, 225.0) or 225.0, 2),
            mean_f0_hz=_sanitize_float(pitch_summary_dict.get("mean_f0_hz")),
            min_f0_hz=_sanitize_float(pitch_summary_dict.get("min_f0_hz")),
            max_f0_hz=_sanitize_float(pitch_summary_dict.get("max_f0_hz")),
            method=pitch_res.method,
            downsampled_timestamps=downsampled_ts,
            downsampled_frequencies=downsampled_f0,
        )

        if pitch_res.voiced_percentage < 15.0 and not pre_res.is_silent:
            warnings.append(
                PipelineWarning(
                    stage="pitch_extraction",
                    code="LOW_VOICED_PERCENTAGE",
                    message=f"Voiced content is low ({pitch_res.voiced_percentage:.1f}%). May be unpitched percussion or heavy ambient noise.",
                )
            )

        # --------------------------------------------------------------------
        # Stage 5: Swara Analysis & Mapping
        # --------------------------------------------------------------------
        self._check_cancellation(cancellation_check)
        self._report_progress(progress_callback, 60, "Swara analysis")

        t0 = time.perf_counter()
        swara_res: SwaraAnalysisResult = self.swara_analyzer.analyze(
            pitch_result=pitch_res,
            tonic_input=resolved_tonic_hz,
        )
        stage_timings["swara_analysis"] = round((time.perf_counter() - t0) * 1000.0, 2)

        # Top transitions
        from collections import Counter
        trans_counts = Counter(swara_res.transitions)
        top_transitions: List[Dict[str, Any]] = []
        for (from_s, to_s), count in trans_counts.most_common(5):
            top_transitions.append({"from": str(from_s), "to": str(to_s), "count": int(count)})

        dominant_swaras_list = [s for s, _ in swara_res.dominant_swaras] if swara_res.dominant_swaras else []
        active_swaras_list = [sym for sym, weight in swara_res.pitch_class_distribution.items() if weight >= 0.015]

        # Calculate mean microtonal cents deviation on voiced frames
        cents_dev_arr = swara_res.cents_from_swara_center
        voiced_conf = swara_res.confidence_values
        mean_cents_dev = 0.0
        if len(cents_dev_arr) > 0 and len(voiced_conf) > 0:
            valid_mask = (voiced_conf > 0.2) & np.isfinite(cents_dev_arr)
            if np.any(valid_mask):
                mean_cents_dev = float(np.mean(np.abs(cents_dev_arr[valid_mask])))

        swara_payload = PipelineSwaraSummary(
            pitch_class_distribution={k: round(_sanitize_float(v, 0.0) or 0.0, 4) for k, v in swara_res.pitch_class_distribution.items()},
            active_swaras=active_swaras_list,
            total_segments=len(swara_res.segments),
            mean_cents_deviation=round(_sanitize_float(mean_cents_dev, 0.0) or 0.0, 2),
            dominant_swaras=dominant_swaras_list,
            transitions_top=top_transitions,
        )

        # --------------------------------------------------------------------
        # Stage 6: Raga Detection & Melodic Motif Matching
        # --------------------------------------------------------------------
        self._check_cancellation(cancellation_check)
        self._report_progress(progress_callback, 70, "Raga detection")

        t0 = time.perf_counter()
        raga_res: RagaAnalysisResult = self.raga_detector.detect(
            swara_result=swara_res,
            tonic_input=resolved_tonic_hz,
            pitch_result=pitch_res,
        )
        stage_timings["raga_detection"] = round((time.perf_counter() - t0) * 1000.0, 2)

        top_cand = raga_res.top_candidates[0] if raga_res.top_candidates else None
        kb_entry = RAGA_KNOWLEDGE_BASE.get(top_cand.raga_id, {}) if top_cand else {}

        # Raga alternatives
        raga_alts: List[PipelineRagaAlternative] = []
        for cand in raga_res.top_candidates[1:5]:
            raga_alts.append(
                PipelineRagaAlternative(
                    raga_id=cand.raga_id,
                    name=cand.raga_name,
                    thaat=cand.thaat,
                    confidence=_clamp_confidence(cand.confidence),
                    composite_score=round(_sanitize_float(cand.score, 0.0) or 0.0, 4),
                )
            )

        # Motif matches
        motif_matches_payload: List[PipelineMotifMatch] = []
        if top_cand and top_cand.motif_evidence and hasattr(top_cand.motif_evidence, "matched_motifs"):
            for m_str in top_cand.motif_evidence.matched_motifs:
                tokens = m_str.split()
                motif_matches_payload.append(
                    PipelineMotifMatch(
                        motif=tokens,
                        motif_str=m_str,
                        match_type="pakad_match",
                        matched_subsequence=tokens,
                        similarity_score=_clamp_confidence(top_cand.motif_evidence.match_score),
                    )
                )
        elif raga_res.phrase_evidence:
            for phrase in raga_res.phrase_evidence:
                motif_matches_payload.append(
                    PipelineMotifMatch(
                        motif=[phrase],
                        motif_str=phrase,
                        match_type="phrase_evidence",
                        matched_subsequence=[phrase],
                        similarity_score=1.0,
                    )
                )

        is_raga_ambiguous = any("ambiguous" in str(lim).lower() for lim in raga_res.limitations)
        raga_name_display = raga_res.detected_raga if raga_res.detected_raga != "INSUFFICIENT_EVIDENCE" else (top_cand.raga_name if top_cand else None)

        raga_payload = PipelineRagaResult(
            predicted_raga=raga_name_display,
            predicted_raga_id=top_cand.raga_id if top_cand else None,
            thaat=top_cand.thaat if top_cand else kb_entry.get("thaat"),
            time=top_cand.time if top_cand else kb_entry.get("time"),
            mood=top_cand.mood if top_cand else kb_entry.get("mood"),
            vadi=kb_entry.get("vadi"),
            samvadi=kb_entry.get("samvadi"),
            aroha=kb_entry.get("aroha", []),
            avaroha=kb_entry.get("avaroha", []),
            confidence=_clamp_confidence(raga_res.confidence),
            is_ambiguous=is_raga_ambiguous,
            alternatives=raga_alts,
            motif_matches=motif_matches_payload,
        )

        if is_raga_ambiguous:
            warnings.append(
                PipelineWarning(
                    stage="raga_detection",
                    code="RAGA_AMBIGUOUS",
                    message="Melodic evidence exhibits close overlap with multiple allied ragas.",
                )
            )

        # --------------------------------------------------------------------
        # Stage 7: Rhythm Feature Extraction (Novelty & Tempo)
        # --------------------------------------------------------------------
        self._check_cancellation(cancellation_check)
        self._report_progress(progress_callback, 80, "Rhythm / beat analysis")

        t0 = time.perf_counter()
        rhythm_features: RhythmFeatures = self.rhythm_analyzer.analyze(
            waveform=pre_res.waveform,
            sample_rate=pre_res.sample_rate,
        )
        stage_timings["rhythm_analysis"] = round((time.perf_counter() - t0) * 1000.0, 2)

        bpm_est = _sanitize_float(rhythm_features.estimated_bpm)
        rhythm_payload = PipelineRhythmSummary(
            estimated_bpm=round(bpm_est, 1) if bpm_est is not None else None,
            laya=_classify_laya(bpm_est),
            tempo_confidence=_clamp_confidence(rhythm_features.tempo_confidence),
            total_onsets=rhythm_features.total_onsets,
            frame_rate=round(_sanitize_float(rhythm_features.frame_rate, 100.0) or 100.0, 2),
        )

        # --------------------------------------------------------------------
        # Stage 8: Tala Classification & Beat Grid Tracking
        # --------------------------------------------------------------------
        self._check_cancellation(cancellation_check)
        self._report_progress(progress_callback, 90, "Tala classification")

        t0 = time.perf_counter()
        tala_res: TalaClassificationResult = self.tala_classifier.classify(rhythm_features)
        stage_timings["tala_classification"] = round((time.perf_counter() - t0) * 1000.0, 2)

        t0 = time.perf_counter()
        beat_grid: BeatGrid = self.beat_tracker.track(
            rhythm_features,
            cycle_length=tala_res.predicted_matras,
        )
        stage_timings["beat_tracking"] = round((time.perf_counter() - t0) * 1000.0, 2)

        self._check_cancellation(cancellation_check)
        self._report_progress(progress_callback, 98, "Finalization")

        # Tala Candidates
        tala_cands_payload: List[PipelineTalaCandidate] = []
        for tc in tala_res.candidates:
            tala_cands_payload.append(
                PipelineTalaCandidate(
                    tala_id=tc.tala_id,
                    name=tc.tala_name,
                    matras=tc.matras,
                    confidence=_clamp_confidence(tc.confidence),
                    composite_score=round(_sanitize_float(tc.composite_score, 0.0) or 0.0, 4),
                )
            )

        # Lookup Tala canonical definition for structure & theka
        tala_def = get_tala(tala_res.predicted_tala_id) if tala_res.predicted_tala_id else None
        vibhag_str = None
        theka_str = None
        sam_pos = 1
        khali_pos: List[int] = []
        tali_pos: List[int] = []

        if tala_def:
            vibhag_str = "+".join(str(v) for v in tala_def.vibhag_structure)
            theka_str = " ".join(tala_def.theka_syllables)
            sam_pos = tala_def.sam_position
            khali_pos = list(tala_def.khali_positions)
            tali_pos = list(tala_def.tali_positions)

        tala_payload = PipelineTalaResult(
            predicted_tala=tala_res.predicted_tala,
            predicted_tala_id=tala_res.predicted_tala_id,
            matras=tala_res.predicted_matras,
            vibhag_structure=vibhag_str,
            theka=theka_str,
            sam_position=sam_pos,
            khali_positions=khali_pos,
            tali_positions=tali_pos,
            confidence=_clamp_confidence(tala_res.confidence),
            is_ambiguous=bool(tala_res.is_ambiguous),
            candidates=tala_cands_payload,
            tempo_hypothesis=tala_res.tempo_hypothesis,
        )

        if tala_res.is_ambiguous:
            warnings.append(
                PipelineWarning(
                    stage="tala_classification",
                    code="TALA_AMBIGUOUS",
                    message="Rhythmic periodicity scores are closely distributed across candidate cycles.",
                )
            )

        # Beat grid payload
        sam_ts_list = []
        if beat_grid.sam_timestamps is not None and len(beat_grid.sam_timestamps) > 0:
            sam_ts_list = [round(float(ts), 3) for ts in beat_grid.sam_timestamps[:20]]

        first_beat = round(float(beat_grid.beat_times[0]), 3) if len(beat_grid.beat_times) > 0 else None
        beat_grid_payload = PipelineBeatGridSummary(
            beat_count=len(beat_grid.beat_times),
            beat_period=round(_sanitize_float(beat_grid.beat_period, 0.0) or 0.0, 4),
            bpm=round(_sanitize_float(beat_grid.bpm), 1) if beat_grid.bpm is not None else None,
            confidence=_clamp_confidence(beat_grid.confidence),
            selected_hypothesis=beat_grid.selected_hypothesis,
            first_beat_time=first_beat,
            sam_timestamps=sam_ts_list,
            cycle_length=beat_grid.cycle_length,
        )

        total_time_ms = round((time.perf_counter() - start_total) * 1000.0, 2)

        return UnifiedAnalysisResult(
            audio_metadata=audio_meta,
            tonic=tonic_payload,
            pitch=pitch_payload,
            swara=swara_payload,
            raga=raga_payload,
            rhythm=rhythm_payload,
            beat_grid=beat_grid_payload,
            tala=tala_payload,
            warnings=warnings,
            processing_time_ms=total_time_ms,
            stage_timings_ms=stage_timings,
        )
