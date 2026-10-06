"""
Pydantic API request and response schemas for audio analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class AudioMetadataSchema(BaseModel):
    """Metadata describing the ingested audio file."""
    model_config = ConfigDict(extra="ignore")

    filename: Optional[str] = Field(default=None, description="Client original or sanitized filename")
    duration_seconds: float = Field(..., ge=0.0, description="Audio duration in seconds")
    sample_rate: int = Field(default=22050, description="Standardized sampling rate in Hz")
    channels: int = Field(default=1, ge=1, description="Original channel count")
    format: Optional[str] = Field(default=None, description="Inferred audio container format")
    is_silent: bool = Field(default=False, description="Flag indicating near-zero acoustic energy")
    rms: float = Field(default=0.0, ge=0.0, description="Root mean square energy")
    peak_amplitude: float = Field(default=0.0, ge=0.0, le=1.0, description="Peak normalized amplitude")


class TonicResultSchema(BaseModel):
    """Resolved tonic fundamental frequency information."""
    model_config = ConfigDict(extra="ignore")

    frequency_hz: Optional[float] = Field(default=None, description="Resolved Sa fundamental frequency in Hz")
    note_name: str = Field(default="Unknown", description="Western 12-TET equivalent note (e.g. 'D3', 'C#3')")
    octave: Optional[int] = Field(default=None, description="Estimated MIDI octave register")
    cents_deviation: Optional[float] = Field(default=None, description="Deviation in cents from nearest equal temperament pitch")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Calibrated tonic resolution confidence")
    is_ambiguous: bool = Field(default=False, description="Flag indicating closely contested runner-up pitch candidates")
    runner_up_hz: Optional[float] = Field(default=None, description="Frequency of runner-up candidate if ambiguous")


class PitchSummarySchema(BaseModel):
    """Summary of continuous pitch track."""
    model_config = ConfigDict(extra="ignore")

    total_frames: int = Field(default=0, ge=0)
    voiced_frames: int = Field(default=0, ge=0)
    voiced_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    frame_rate: float = Field(default=225.0, ge=0.0)
    mean_f0_hz: Optional[float] = Field(default=None, ge=0.0)
    min_f0_hz: Optional[float] = Field(default=None, ge=0.0)
    max_f0_hz: Optional[float] = Field(default=None, ge=0.0)
    method: str = Field(default="yin_parabolic")
    downsampled_timestamps: List[float] = Field(default_factory=list, description="Downsampled time coordinates (seconds)")
    downsampled_frequencies: List[float] = Field(default_factory=list, description="Downsampled voiced frequencies (Hz)")


class SwaraSummarySchema(BaseModel):
    """Summary of Indian classical swara mapping and distribution."""
    model_config = ConfigDict(extra="ignore")

    pitch_class_distribution: Dict[str, float] = Field(default_factory=dict, description="Normalized 12-Swara PCD histogram")
    active_swaras: List[str] = Field(default_factory=list, description="Swaras exceeding activation threshold")
    total_segments: int = Field(default=0, ge=0, description="Count of discrete sustained swara note events")
    mean_cents_deviation: float = Field(default=0.0, description="Average microtonal deviation in cents")
    dominant_swaras: List[str] = Field(default_factory=list, description="Top 3 most frequent swaras in performance")
    transitions_top: List[Dict[str, Any]] = Field(default_factory=list, description="Top melodic bigram transitions")


class MotifEvidenceSchema(BaseModel):
    """Evidence of detected melodic pakad / catch phrase motif."""
    model_config = ConfigDict(extra="ignore")

    motif: List[str] = Field(..., description="Canonical motif swara sequence")
    motif_str: str = Field(..., description="Formatted swara phrase string")
    match_type: str = Field(..., description="exact, collapsed, or fuzzy")
    matched_subsequence: List[str] = Field(..., description="Matched swara tokens in recording")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Match score")
    start_time_seconds: Optional[float] = None
    end_time_seconds: Optional[float] = None


class RagaAlternativeSchema(BaseModel):
    """Alternative candidate raga hypothesis."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Alternative raga identifier")
    name: str = Field(..., description="Display name")
    thaat: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    composite_score: float = 0.0


class RagaResultSchema(BaseModel):
    """Identified Raga and theoretical attributes."""
    model_config = ConfigDict(extra="ignore")

    id: Optional[str] = Field(default=None, description="Top predicted raga identifier")
    name: Optional[str] = Field(default=None, description="Top predicted raga display name")
    thaat: Optional[str] = None
    time: Optional[str] = None
    mood: Optional[str] = None
    vadi: Optional[str] = None
    samvadi: Optional[str] = None
    aroha: List[str] = Field(default_factory=list)
    avaroha: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_ambiguous: bool = Field(default=False)
    alternatives: List[RagaAlternativeSchema] = Field(default_factory=list)
    motif_matches: List[MotifEvidenceSchema] = Field(default_factory=list)


class RhythmSummarySchema(BaseModel):
    """Summary of rhythmic onset and tempo extraction."""
    model_config = ConfigDict(extra="ignore")

    estimated_bpm: Optional[float] = Field(default=None, ge=0.0)
    laya: str = Field(default="Unknown", description="Hindustani tempo class (Vilambit, Madhya, Drut)")
    tempo_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    total_onsets: int = Field(default=0, ge=0)
    frame_rate: float = Field(default=100.0, ge=0.0)


class BeatGridSummarySchema(BaseModel):
    """Summary of dynamic beat tracking and Sam boundaries."""
    model_config = ConfigDict(extra="ignore")

    beat_count: int = Field(default=0, ge=0)
    beat_period: float = Field(default=0.0, ge=0.0)
    bpm: Optional[float] = Field(default=None, ge=0.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    selected_hypothesis: str = Field(default="1.0x")
    first_beat_time: Optional[float] = None
    sam_timestamps: List[float] = Field(default_factory=list)
    cycle_length: Optional[int] = None


class TalaCandidateSchema(BaseModel):
    """Candidate Tala evaluation."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Tala identifier")
    name: str = Field(..., description="Display name")
    matras: int = Field(..., ge=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    composite_score: float = 0.0


class TalaResultSchema(BaseModel):
    """Classified Tala rhythmic cycle and structure."""
    model_config = ConfigDict(extra="ignore")

    id: Optional[str] = Field(default=None, description="Top predicted Tala identifier")
    name: Optional[str] = Field(default=None, description="Top predicted Tala name")
    matras: Optional[int] = Field(default=None, ge=1)
    beats: Optional[int] = Field(default=None, ge=1)
    vibhag_structure: Optional[str] = Field(default=None, description="Partitions joined by '+'")
    theka: Optional[str] = Field(default=None, description="Theka bols")
    sam_position: Optional[int] = Field(default=1, ge=1)
    khali_positions: List[int] = Field(default_factory=list)
    tali_positions: List[int] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_ambiguous: bool = Field(default=False)
    candidates: List[TalaCandidateSchema] = Field(default_factory=list)
    tempo_hypothesis: str = Field(default="1.0x")


class AnalysisWarningSchema(BaseModel):
    """Warning emitted during analysis."""
    stage: str
    code: str
    message: str


class AnalysisResponse(BaseModel):
    """Complete, unified API response for audio analysis."""
    model_config = ConfigDict(extra="ignore")

    analysis_id: str = Field(..., description="Unique analysis job UUID")
    status: Literal["completed", "processing", "failed"] = Field(default="completed")
    audio_metadata: AudioMetadataSchema
    tonic: TonicResultSchema
    pitch: PitchSummarySchema
    swara: SwaraSummarySchema
    raga: RagaResultSchema
    rhythm: RhythmSummarySchema
    beat_grid: BeatGridSummarySchema
    tala: TalaResultSchema
    warnings: List[AnalysisWarningSchema] = Field(default_factory=list)
    processing_time_ms: float = Field(default=0.0, ge=0.0)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class JobErrorSchema(BaseModel):
    """Sanitized, safe error description for failed jobs."""
    model_config = ConfigDict(extra="ignore")

    code: str = Field(..., description="Machine-readable error classification code")
    message: str = Field(..., description="Human-readable sanitized error message")


class AnalysisJobStatusResponse(BaseModel):
    """API response model representing the asynchronous state of an analysis job."""
    model_config = ConfigDict(extra="ignore")

    job_id: str = Field(..., description="Unique analysis job UUID")
    status: Literal["QUEUED", "PROCESSING", "COMPLETED", "FAILED", "CANCELLED"] = Field(..., description="Job lifecycle status")
    progress: int = Field(default=0, ge=0, le=100, description="Monotonically increasing progress percentage 0-100")
    current_stage: str = Field(default="Initialization", description="Current pipeline execution stage")
    created_at: str = Field(..., description="ISO 8601 UTC creation timestamp")
    started_at: Optional[str] = Field(default=None, description="ISO 8601 UTC execution start timestamp")
    completed_at: Optional[str] = Field(default=None, description="ISO 8601 UTC completion timestamp")
    result: Optional[AnalysisResponse] = Field(default=None, description="Analysis result payload when COMPLETED")
    error: Optional[JobErrorSchema] = Field(default=None, description="Error details when FAILED")


class AnalysisJobCancelResponse(BaseModel):
    """Response returned when cancellation is requested on a job."""
    model_config = ConfigDict(extra="ignore")

    job_id: str = Field(..., description="Unique job identifier UUID")
    status: Literal["QUEUED", "PROCESSING", "COMPLETED", "FAILED", "CANCELLED"] = Field(..., description="Status after cancellation request")
    message: str = Field(..., description="Description of cancellation action taken")

