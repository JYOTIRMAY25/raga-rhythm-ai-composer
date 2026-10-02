"""
Tala domain and catalog response schemas.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TalaSchema(BaseModel):
    """Structured representation of a canonical Indian classical rhythmic cycle (Tala)."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Canonical snake_case tala identifier (e.g. 'teental')")
    name: str = Field(..., description="Canonical display name (e.g. 'Teental')")
    matras: int = Field(..., ge=1, description="Total beat count in one Avartan")
    beats: int = Field(..., ge=1, description="Alias for total beat count")
    vibhag_structure: List[int] = Field(..., description="Measure partitions (e.g. [4, 4, 4, 4])")
    vibhag: str = Field(..., description="String partition format (e.g. '4+4+4+4')")
    sam_position: int = Field(default=1, ge=1, description="1-indexed position of Sam")
    khali_positions: List[int] = Field(default_factory=list, description="1-indexed positions of Khali (waves)")
    tali_positions: List[int] = Field(default_factory=list, description="1-indexed positions of Tali (claps)")
    theka: str = Field(..., description="Canonical mnemonic drum syllables joined by spaces")
    pattern: str = Field(..., description="Full pattern formatting with vibhag division bars")
    theka_syllables: List[str] = Field(default_factory=list, description="Individual bol list")
    aliases: List[str] = Field(default_factory=list, description="Alternative names")
    description: Optional[str] = Field(default=None, description="Rhythmic context and performance notes")


class TalaListResponse(BaseModel):
    """Response payload for tala catalog queries."""
    model_config = ConfigDict(extra="forbid")

    total: int = Field(..., description="Total count of matching talas")
    talas: List[TalaSchema] = Field(..., description="List of tala records")
