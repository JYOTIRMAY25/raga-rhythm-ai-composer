"""
Pydantic models and data structures for algorithmic composition representation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SwaraEvent(BaseModel):
    """Represents a single discrete melodic/rhythmic swara event."""
    model_config = ConfigDict(extra="ignore")

    cycle: int = Field(..., ge=1, description="Cycle index (1-indexed)")
    vibhag: int = Field(..., ge=1, description="Vibhag measure index within cycle (1-indexed)")
    matra: int = Field(..., ge=1, description="Matra beat position within cycle (1-indexed)")
    subdivision: int = Field(default=0, ge=0, description="Subdivision within matra (0 for on-beat, 1..3 for fractional)")
    swara: str = Field(..., description="Canonical Swara name (e.g., 'S', 'r', 'R', 'g', 'G', 'm', 'M', 'P', 'd', 'D', 'n', 'N') with optional octave suffix (e.g., 'N.', 'S', 'R'')")
    octave: int = Field(default=0, description="Octave offset (-1: Mandra, 0: Madhya, +1: Tara)")
    pitch_hz: float = Field(..., gt=0, description="Exact fundamental frequency in Hz relative to Sa tonic")
    duration_matras: float = Field(default=1.0, gt=0, description="Duration of this note event in matra beats")
    theka_bol: Optional[str] = Field(None, description="Accompanying percussion bol on this beat (e.g., 'Dha', 'Dhin', 'Ta')")
    ornament: Optional[str] = Field("straight", description="Ornamentation style ('straight', 'meend', 'kan', 'andolan', 'gamak')")
    is_vadi: bool = Field(default=False, description="Whether this swara is the king note (Vadi) of the raga")
    is_samvadi: bool = Field(default=False, description="Whether this swara is the queen/minister note (Samvadi)")
    is_sam_landing: bool = Field(default=False, description="True if this event lands exactly on Sam (beat 1)")


class CompositionCycle(BaseModel):
    """Represents one complete Tala metric cycle in the composition."""
    model_config = ConfigDict(extra="ignore")

    cycle_number: int = Field(..., ge=1)
    events: List[SwaraEvent] = Field(default_factory=list)


class ValidationDiagnostic(BaseModel):
    """Diagnostic notice, warning, or error from the composition validator."""
    model_config = ConfigDict(extra="ignore")

    severity: str = Field(..., description="'error', 'warning', or 'info'")
    rule: str = Field(..., description="Musicological rule or invariant evaluated")
    message: str = Field(..., description="Human-readable explanation of diagnostic")
    location: Optional[str] = Field(None, description="Cycle/matra location where rule triggered")


class ValidationResult(BaseModel):
    """Comprehensive validation outcome for generated composition."""
    model_config = ConfigDict(extra="ignore")

    valid: bool = Field(..., description="True if composition strictly satisfies all musicological invariants")
    swara_compliance_score: float = Field(..., ge=0.0, le=1.0, description="Ratio of swaras adhering to raga scale")
    tala_alignment_score: float = Field(..., ge=0.0, le=1.0, description="Metric adherence to Tala cycle and vibhags")
    sam_resolution_passed: bool = Field(..., description="Whether cadential phrases resolve appropriately to Sam")
    diagnostics: List[ValidationDiagnostic] = Field(default_factory=list)


class SymbolicComposition(BaseModel):
    """Full symbolic representation of the generated classical composition."""
    model_config = ConfigDict(extra="ignore")

    composition_id: str = Field(..., description="Unique composition UUID")
    title: str = Field(..., description="Descriptive title of generated composition")
    raga_id: str = Field(..., description="Canonical raga identifier")
    raga_name: str = Field(..., description="Display name of Raga")
    thaat: str = Field(..., description="Parent Thaat")
    tala_id: str = Field(..., description="Canonical tala identifier")
    tala_name: str = Field(..., description="Display name of Tala")
    matras: int = Field(..., ge=1, description="Total matras per cycle")
    vibhag_structure: str = Field(..., description="Vibhag partition structure (e.g. '4+4+4+4')")
    tempo_bpm: int = Field(..., ge=40, le=240, description="Tempo in BPM")
    laya: str = Field(..., description="Laya category ('Vilambit', 'Madhya', 'Drut')")
    tonic_note: str = Field(..., description="Adhara Shadja tonic note name (e.g., 'C', 'D#')")
    tonic_hz: float = Field(..., gt=0, description="Adhara Shadja frequency in Hz")
    style: str = Field(..., description="Stylistic genre ('khayal', 'bandish', 'alap_gat', 'dhrupad')")
    total_cycles: int = Field(..., ge=1, description="Total number of Tala cycles")
    total_matras: int = Field(..., ge=1, description="Total composition length in matras")
    duration_seconds: float = Field(..., gt=0, description="Total computed duration in seconds")
    events: List[SwaraEvent] = Field(default_factory=list, description="Linear timeline of all note events")
    cycles: List[CompositionCycle] = Field(default_factory=list, description="Cycle-grouped events")
    seed: int = Field(..., description="PRNG seed used for deterministic reproduction")
    validation: ValidationResult
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CompositionRequest(BaseModel):
    """Request payload for composition generation."""
    model_config = ConfigDict(extra="ignore")

    raga_id: str = Field(default="yaman", description="Target canonical Raga ID")
    tala_id: str = Field(default="teental", description="Target Tala ID")
    tonic: Optional[str] = Field(default="C", description="Tonic note name (e.g., 'C', 'C#', 'D')")
    tonic_hz: Optional[float] = Field(default=None, description="Explicit tonic frequency in Hz")
    tempo_bpm: int = Field(default=84, ge=40, le=240, description="Tempo in BPM")
    duration_seconds: int = Field(default=60, ge=15, le=300, description="Target duration in seconds")
    style_id: str = Field(default="bandish", description="Style / structure ('bandish', 'alap', 'drut_gat')")
    creativity_score: int = Field(default=50, ge=0, le=100, description="Creativity level [0-100]")
    seed: Optional[int] = Field(default=None, description="Optional integer seed for deterministic reproduction")
    tuning_mode: Optional[str] = Field(default="canonical", description="Intonation tuning mode ('canonical' or 'raga_aware')")
    timbre: Optional[str] = Field(default="ensemble", description="Synthesizer timbre ('ensemble', 'flute', 'bowed')")


class CompositionResponse(BaseModel):
    """API Response payload containing generated composition and diagnostics."""
    model_config = ConfigDict(extra="ignore")

    composition_id: str
    title: str
    metadata: Dict[str, Any]
    symbolic_composition: SymbolicComposition
    validation_result: ValidationResult
    warnings: List[str] = Field(default_factory=list)
    audio_available: bool = Field(default=True, description="Indicates WAV audio synthesis is available")
    audio_duration_seconds: Optional[float] = Field(default=None, description="Exact synthesized audio duration in seconds")
    audio_url: Optional[str] = Field(default=None, description="Direct download URL or audio stream endpoint")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
