"""
Pydantic schemas for Gemini AI natural-language musical explanation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class GeminiExplanationRequest(BaseModel):
    """Input payload for generating an AI explanation of music analysis."""
    model_config = ConfigDict(extra="ignore")

    raga_name: Optional[str] = Field(None, description="Primary detected raga name")
    raga_id: Optional[str] = Field(None, description="Primary detected raga ID")
    thaat: Optional[str] = Field(None, description="Raga parent Thaat")
    time_of_day: Optional[str] = Field(None, description="Traditional performance time")
    vadi: Optional[str] = Field(None, description="King note (Vadi)")
    samvadi: Optional[str] = Field(None, description="Queen/Minister note (Samvadi)")
    aroha: Optional[List[str]] = Field(default_factory=list, description="Ascending scale")
    avaroha: Optional[List[str]] = Field(default_factory=list, description="Descending scale")
    tonic_note: Optional[str] = Field(None, description="Resolved Sa tonic note name")
    tonic_hz: Optional[float] = Field(None, description="Resolved Sa tonic frequency in Hz")
    tonic_confidence: Optional[float] = Field(None, description="Tonic resolution confidence")
    tala_name: Optional[str] = Field(None, description="Detected Tala name")
    matras: Optional[int] = Field(None, description="Number of beats in Tala cycle")
    vibhag_structure: Optional[str] = Field(None, description="Vibhag division structure")
    theka: Optional[str] = Field(None, description="Theka bols string")
    bpm: Optional[float] = Field(None, description="Estimated tempo in BPM")
    laya: Optional[str] = Field(None, description="Laya speed category (Vilambit/Madhya/Drut)")
    dominant_swaras: Optional[List[str]] = Field(default_factory=list, description="Top dominant swaras in audio")
    pitch_class_distribution: Optional[Dict[str, float]] = Field(default_factory=dict, description="12-swara PCD")
    motifs_detected: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Pakad motifs detected")
    raga_confidence: Optional[float] = Field(None, description="Raga detection confidence")
    is_ambiguous: Optional[bool] = Field(False, description="Whether raga classification is ambiguous")
    alternatives: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Allied raga candidates")
    warnings: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Diagnostic warnings")


class GeminiAnalysisExplanation(BaseModel):
    """Structured, verified natural-language explanation of machine analysis."""
    model_config = ConfigDict(extra="ignore")

    available: bool = Field(..., description="Whether live Gemini API generated this explanation")
    summary: str = Field(..., description="Executive musicological summary of the audio analysis")
    tonic_explanation: str = Field(..., description="Explanation of the detected tonic (Sa) and its acoustic role")
    raga_explanation: str = Field(..., description="In-depth explanation of the raga, mood (rasa), time, and melodic rules")
    swara_explanation: str = Field(..., description="Explanation of the swara distribution and prominent notes")
    rhythm_explanation: str = Field(..., description="Explanation of the tempo (laya) and rhythmic dynamics")
    tala_explanation: str = Field(..., description="Explanation of the rhythmic cycle (tala), vibhags, and sam")
    confidence_notes: str = Field(..., description="Interpretation of machine confidence scores and ambiguity")
    warnings: List[str] = Field(default_factory=list, description="Key alerts and acoustic notices")
    educational_notes: List[str] = Field(default_factory=list, description="Educational insights for classical music students")
    model_used: Optional[str] = Field(None, description="Gemini model version or 'deterministic-rule-engine'")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
