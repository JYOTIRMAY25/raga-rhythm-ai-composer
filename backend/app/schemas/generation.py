"""
Pydantic API request and response schemas for composition generation (contract definition).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class GenerationRequest(BaseModel):
    """Configuration settings for algorithmic / AI music generation."""
    model_config = ConfigDict(extra="forbid")

    raga_id: str = Field(..., description="Target canonical Raga identifier (e.g. 'yaman', 'bhairavi')")
    tala_id: str = Field(..., description="Target Tala rhythmic cycle (e.g. 'teental', 'jhaptal')")
    style_id: str = Field(default="khayal", description="Performance style / genre (e.g. 'khayal', 'dhrupad', 'instrumental')")
    tempo_bpm: int = Field(default=84, ge=40, le=240, description="Tempo in beats per minute")
    duration_seconds: int = Field(default=60, ge=15, le=300, description="Target composition duration in seconds")
    creativity_score: int = Field(default=50, ge=0, le=100, description="Algorithmic improvisation / temperature [0-100]")


class GenerationSummaryItem(BaseModel):
    id: str
    name: str
    beats: Optional[int] = None


class GenerationResponse(BaseModel):
    """Structured response representing a generated composition."""
    model_config = ConfigDict(extra="forbid")

    composition_id: str = Field(..., description="Unique generated composition identifier")
    raga: GenerationSummaryItem
    tala: GenerationSummaryItem
    style: GenerationSummaryItem
    tempo_bpm: int = Field(..., ge=40, le=240)
    duration_seconds: int = Field(..., ge=15, le=300)
    creativity_score: int = Field(..., ge=0, le=100)
    audio_url: str = Field(..., description="Relative or absolute URL to stream/download generated composition")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
