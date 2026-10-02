"""
Raga domain and catalog response schemas.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RagaSchema(BaseModel):
    """Structured representation of a canonical Indian classical raga."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Canonical snake_case raga identifier (e.g. 'yaman')")
    name: str = Field(..., description="Canonical display name (e.g. 'Yaman')")
    thaat: Optional[str] = Field(default=None, description="Parent Thaat / scale family")
    time: Optional[str] = Field(default=None, description="Traditional performance prahar / time of day")
    mood: Optional[str] = Field(default=None, description="Rasa / emotional ethos")
    vadi: Optional[str] = Field(default=None, description="Vadi (primary sovereign) swara")
    samvadi: Optional[str] = Field(default=None, description="Samvadi (secondary consonant) swara")
    swaras: List[str] = Field(default_factory=list, description="Constituent swara symbols")
    varjit: List[str] = Field(default_factory=list, description="Varjit (omitted) swaras")
    aroha: List[str] = Field(default_factory=list, description="Ascending scale structure")
    avaroha: List[str] = Field(default_factory=list, description="Descending scale structure")
    pakad_motifs: List[List[str]] = Field(default_factory=list, description="Canonical catch phrases / motifs")
    aliases: List[str] = Field(default_factory=list, description="Alternative spellings or names")
    description: Optional[str] = Field(default=None, description="Musicological summary")


class RagaListResponse(BaseModel):
    """Response payload for raga catalog queries."""
    model_config = ConfigDict(extra="forbid")

    total: int = Field(..., description="Total count of matching ragas")
    ragas: List[RagaSchema] = Field(..., description="List of raga records")
