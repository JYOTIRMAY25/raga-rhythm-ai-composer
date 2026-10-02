"""
Tala Knowledge Base for RagaRhythm AI.

Provides:
1. Strongly typed immutable domain model `TalaDefinition` with strict invariant validation.
2. Canonical definitions of core Hindustani Talas (Teental, Dadra, Keharwa, Rupak, Jhaptaal, Ektaal).
3. Fast, normalized, case-insensitive lookup and query APIs.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Set

from pydantic import BaseModel, ConfigDict, Field, model_validator

logger = logging.getLogger(__name__)


def _strip_accents(text: str) -> str:
    """Strip unicode diacritical marks (e.g., 'Tīntāl' -> 'Tintal')."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_tala_lookup_key(name: Optional[str]) -> str:
    """
    Standardize a tala name or query string into a canonical lookup key.
    
    Handles diacritics, case differences, prefixes/suffixes ('taal', 'tala'),
    underscores, hyphens, and whitespace.
    
    Examples:
        'Teental' -> 'teental'
        'Tīntāl' -> 'teental'
        'Taal Ektaal' -> 'ektaal'
        'Jhap Taal' -> 'jhaptaal'
        'ROOPAK' -> 'rupak'
    """
    if not name or not isinstance(name, str):
        return ""
    
    clean = _strip_accents(name.strip()).lower()
    # Strip leading/trailing taal/tala/tal words
    clean = re.sub(r'^(taal|tala|tal)\s+', '', clean)
    clean = re.sub(r'\s+(taal|tala|tal)$', '', clean)
    clean = re.sub(r'[\(\)\[\],_\-\/]', ' ', clean)
    clean = re.sub(r'\s+', '', clean).strip()

    ALIAS_MAP: Dict[str, str] = {
        "teentaal": "teental",
        "teental": "teental",
        "tintal": "teental",
        "tintaal": "teental",
        "tritala": "teental",
        "trital": "teental",
        "ektaal": "ektaal",
        "ektal": "ektaal",
        "ekatala": "ektaal",
        "ekatali": "ektaal",
        "jhaptaal": "jhaptaal",
        "jhaptal": "jhaptaal",
        "jhaptala": "jhaptaal",
        "rupak": "rupak",
        "roopak": "rupak",
        "rupaktal": "rupak",
        "rupaktaal": "rupak",
        "keherwa": "keharwa",
        "keharwa": "keharwa",
        "kaharwa": "keharwa",
        "kaharva": "keharwa",
        "dadra": "dadra",
        "dhadra": "dadra",
        "tilwada": "tilwada",
        "tilavada": "tilwada",
        "jhoomra": "jhoomra",
        "jhumra": "jhumra",
        "deepchandi": "deepchandi",
        "dipchandi": "deepchandi",
    }

    return ALIAS_MAP.get(clean, clean)


class TalaDefinition(BaseModel):
    """
    Strongly typed, immutable domain model for a Tala (rhythmic cycle) definition.
    
    Invariants enforced:
    1. name and tala_id must be non-empty strings.
    2. matras > 0.
    3. sum(vibhag_structure) == matras, with every vibhag > 0.
    4. theka_syllables length == matras, with each syllable non-empty.
    5. sam_position is within 1..matras.
    6. khali_positions are within 1..matras, with no duplicate positions.
    7. tali_positions are within 1..matras, with no duplicate positions.
    8. khali_positions and tali_positions are mutually disjoint.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Canonical display name (e.g. 'Teental')")
    tala_id: str = Field(..., description="Canonical identifier (e.g. 'teental')")
    aliases: List[str] = Field(default_factory=list, description="Common spelling variations and transliterations")
    matras: int = Field(..., description="Total number of beats in one complete avartan (cycle)")
    vibhag_structure: List[int] = Field(..., description="Ordered list of beat counts for each vibhag (measure)")
    sam_position: int = Field(default=1, description="1-indexed beat position of Sam (primary accent)")
    khali_positions: List[int] = Field(default_factory=list, description="1-indexed beat positions of Khali (unaccented wave)")
    tali_positions: List[int] = Field(default_factory=list, description="1-indexed beat positions of Tali (clap accents)")
    theka_syllables: List[str] = Field(..., description="Mnemonic drum bols for each matra in the cycle")
    description: Optional[str] = Field(default=None, description="Musicological summary and performance context")

    @model_validator(mode="after")
    def validate_invariants(self) -> TalaDefinition:
        # Invariant 8: Non-empty name and tala_id
        if not self.name or not self.name.strip():
            raise ValueError("Tala name cannot be empty")
        if not self.tala_id or not self.tala_id.strip():
            raise ValueError("Tala tala_id cannot be empty")

        # Invariant 1: matras > 0
        if self.matras <= 0:
            raise ValueError(f"matras must be positive, got {self.matras}")

        # Invariant 2: sum(vibhag_structure) == matras and each vibhag > 0
        if not self.vibhag_structure:
            raise ValueError("vibhag_structure cannot be empty")
        for v in self.vibhag_structure:
            if v <= 0:
                raise ValueError(f"Each vibhag length must be > 0, got {v} in {self.vibhag_structure}")
        if sum(self.vibhag_structure) != self.matras:
            raise ValueError(
                f"Sum of vibhags ({sum(self.vibhag_structure)}) must equal matras ({self.matras})"
            )

        # Invariant 3: theka_syllables length == matras, each non-empty
        if len(self.theka_syllables) != self.matras:
            raise ValueError(
                f"theka_syllables length ({len(self.theka_syllables)}) must equal matras ({self.matras})"
            )
        for idx, bol in enumerate(self.theka_syllables):
            if not isinstance(bol, str) or not bol.strip():
                raise ValueError(f"theka syllable at index {idx} (beat {idx + 1}) cannot be empty")

        # Invariant 4: sam_position is within 1..matras
        if not (1 <= self.sam_position <= self.matras):
            raise ValueError(f"sam_position ({self.sam_position}) must be within 1..{self.matras}")

        # Invariant 5: khali positions are within 1..matras with no duplicates
        if len(self.khali_positions) != len(set(self.khali_positions)):
            raise ValueError(f"Duplicate khali_positions found: {self.khali_positions}")
        for kp in self.khali_positions:
            if not (1 <= kp <= self.matras):
                raise ValueError(f"khali position ({kp}) must be within 1..{self.matras}")

        # Invariant 6: tali positions are within 1..matras with no duplicates
        if len(self.tali_positions) != len(set(self.tali_positions)):
            raise ValueError(f"Duplicate tali_positions found: {self.tali_positions}")
        for tp in self.tali_positions:
            if not (1 <= tp <= self.matras):
                raise ValueError(f"tali position ({tp}) must be within 1..{self.matras}")

        # Invariant 7: tali_positions and khali_positions must be disjoint
        overlap = set(self.tali_positions).intersection(set(self.khali_positions))
        if overlap:
            raise ValueError(f"Positions cannot be both tali and khali: {sorted(list(overlap))}")

        return self


# ============================================================================
# Canonical Initial Tala Knowledge Base
# ============================================================================

TALA_KNOWLEDGE_BASE: Dict[str, TalaDefinition] = {
    "teental": TalaDefinition(
        name="Teental",
        tala_id="teental",
        aliases=["teentaal", "tintal", "tintaal", "tritala", "trital"],
        matras=16,
        vibhag_structure=[4, 4, 4, 4],
        sam_position=1,
        khali_positions=[9],
        tali_positions=[1, 5, 13],
        theka_syllables=[
            "Dha", "Dhin", "Dhin", "Dha",
            "Dha", "Dhin", "Dhin", "Dha",
            "Dha", "Tin", "Tin", "Ta",
            "Ta", "Dhin", "Dhin", "Dha"
        ],
        description="16-beat symmetrical cycle, 4 vibhags of 4 matras each (3 tali + 1 khali). Most ubiquitous tala in Hindustani classical music."
    ),
    "dadra": TalaDefinition(
        name="Dadra",
        tala_id="dadra",
        aliases=["dadra taal", "dhadra"],
        matras=6,
        vibhag_structure=[3, 3],
        sam_position=1,
        khali_positions=[4],
        tali_positions=[1],
        theka_syllables=[
            "Dha", "Dhin", "Na",
            "Dha", "Tin", "Na"
        ],
        description="6-beat light-classical cycle in 2 equal vibhags of 3 matras (tali on 1, khali on 4)."
    ),
    "keharwa": TalaDefinition(
        name="Keharwa",
        tala_id="keharwa",
        aliases=["keherwa", "kaharwa", "kaharva"],
        matras=8,
        vibhag_structure=[4, 4],
        sam_position=1,
        khali_positions=[5],
        tali_positions=[1],
        theka_syllables=[
            "Dha", "Ge", "Na", "Ti",
            "Na", "Ka", "Dhi", "Na"
        ],
        description="8-beat light-classical/folk cycle in 2 vibhags of 4 matras (tali on 1, khali on 5)."
    ),
    "rupak": TalaDefinition(
        name="Rupak",
        tala_id="rupak",
        aliases=["roopak", "rupaktal", "rupak taal"],
        matras=7,
        vibhag_structure=[3, 2, 2],
        sam_position=1,
        khali_positions=[1],
        tali_positions=[4, 6],
        theka_syllables=[
            "Tin", "Tin", "Na",
            "Dhi", "Na",
            "Dhi", "Na"
        ],
        description="7-beat asymmetric cycle (3+2+2) famously starting on Khali on beat 1, with talis on beats 4 and 6."
    ),
    "jhaptaal": TalaDefinition(
        name="Jhaptaal",
        tala_id="jhaptaal",
        aliases=["jhaptal", "jhap tala", "jhaptaala"],
        matras=10,
        vibhag_structure=[2, 3, 2, 3],
        sam_position=1,
        khali_positions=[6],
        tali_positions=[1, 3, 8],
        theka_syllables=[
            "Dhi", "Na",
            "Dhi", "Dhi", "Na",
            "Ti", "Na",
            "Dhi", "Dhi", "Na"
        ],
        description="10-beat asymmetric cycle in 4 vibhags (2+3+2+3) with talis on 1, 3, 8 and khali on 6."
    ),
    "ektaal": TalaDefinition(
        name="Ektaal",
        tala_id="ektaal",
        aliases=["ektal", "ek tala", "ektaala"],
        matras=12,
        vibhag_structure=[2, 2, 2, 2, 2, 2],
        sam_position=1,
        khali_positions=[3, 7],
        tali_positions=[1, 5, 9, 11],
        theka_syllables=[
            "Dhin", "Dhin",
            "DhaGe", "TirKit",
            "Tu", "Na",
            "Kat", "Ta",
            "DhaGe", "TirKit",
            "Dhi", "Na"
        ],
        description="12-beat cycle in 6 vibhags of 2 matras each, talis on 1, 5, 9, 11 and khalis on 3, 7. Used across Vilambit, Madhya, and Drut tempos."
    ),
}

# Precompute lookup index for alias and normalized key resolution
_LOOKUP_INDEX: Dict[str, str] = {}
for _tid, _tala in TALA_KNOWLEDGE_BASE.items():
    _LOOKUP_INDEX[_tid] = _tid
    _LOOKUP_INDEX[normalize_tala_lookup_key(_tala.name)] = _tid
    for _alias in _tala.aliases:
        _LOOKUP_INDEX[normalize_tala_lookup_key(_alias)] = _tid


# ============================================================================
# Knowledge Base Lookup APIs
# ============================================================================

def get_tala(name: str) -> Optional[TalaDefinition]:
    """
    Look up a TalaDefinition by canonical name, identifier, or alias.
    
    Safe, normalized, and case-insensitive.
    Returns None if no matching tala is found.
    
    Examples:
        >>> get_tala("Teental").matras
        16
        >>> get_tala("teentaal").name
        'Teental'
        >>> get_tala("Taal Ektaal").matras
        12
        >>> get_tala("Unknown")
        None
    """
    if not name or not isinstance(name, str):
        return None
    
    # 1. Direct dictionary key check
    if name in TALA_KNOWLEDGE_BASE:
        return TALA_KNOWLEDGE_BASE[name]
    
    # 2. Normalized lookup key check
    key = normalize_tala_lookup_key(name)
    if key in _LOOKUP_INDEX:
        target_id = _LOOKUP_INDEX[key]
        return TALA_KNOWLEDGE_BASE.get(target_id)
    
    return None


def get_all_talas() -> List[TalaDefinition]:
    """Return an immutable list of all registered canonical TalaDefinitions."""
    return list(TALA_KNOWLEDGE_BASE.values())


def get_talas_by_matras(matras: int) -> List[TalaDefinition]:
    """
    Retrieve all registered TalaDefinitions matching the specified matra count.
    
    Example:
        >>> get_talas_by_matras(16)
        [TalaDefinition(name='Teental', ...)]
    """
    if not isinstance(matras, int) or matras <= 0:
        return []
    return [tala for tala in TALA_KNOWLEDGE_BASE.values() if tala.matras == matras]


def has_tala(name: str) -> bool:
    """Check if a tala exists in the knowledge base by name, id, or alias."""
    return get_tala(name) is not None
