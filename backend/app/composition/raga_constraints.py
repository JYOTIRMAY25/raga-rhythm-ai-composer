"""
Raga musicological constraints, pitch mapping, and rule definitions.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from backend.app.analysis.raga_detector import RAGA_KNOWLEDGE_BASE

# 12-Tone Semitone Multipliers relative to Sa (Just Intonation & Equal Temperament hybrid)
SEMITONE_OFFSETS: Dict[str, int] = {
    "S": 0,
    "r": 1,
    "R": 2,
    "g": 3,
    "G": 4,
    "m": 5,
    "M": 6,
    "M'": 6,
    "P": 7,
    "d": 8,
    "D": 9,
    "n": 10,
    "N": 11,
}

# Standard note name to standard middle octave frequency (Hz)
STANDARD_TONIC_FREQUENCIES: Dict[str, float] = {
    "C": 130.81,
    "C#": 138.59,
    "Db": 138.59,
    "D": 146.83,
    "D#": 155.56,
    "Eb": 155.56,
    "E": 164.81,
    "F": 174.61,
    "F#": 185.00,
    "Gb": 185.00,
    "G": 196.00,
    "G#": 207.65,
    "Ab": 207.65,
    "A": 220.00,
    "A#": 233.08,
    "Bb": 233.08,
    "B": 246.94,
}


def normalize_swara_symbol(swara_raw: str) -> Tuple[str, int]:
    """
    Normalizes a swara string with octave markings into (base_swara, octave_offset).
    Examples:
    'S' -> ('S', 0)
    'N.' or '.N' or 'n.' -> ('N', -1) or ('n', -1)
    'S\'' or 'R\'' or 'G\'' -> ('S', 1) or ('R', 1)
    """
    clean = swara_raw.strip().replace(" ", "")
    octave = 0

    if clean.endswith(".") or clean.startswith("."):
        octave = -1
        clean = clean.replace(".", "")
    elif clean.endswith("'") or clean.startswith("'"):
        octave = 1
        clean = clean.replace("'", "")

    # Handle tivra Ma notation
    if clean.upper() == "M'" or clean == "M":
        clean = "M"
    elif clean.upper() == "MA":
        clean = "m"

    return clean, octave


class RagaConstraints:
    """Encapsulates all musicological rules and scale boundaries for a specific Raga."""

    def __init__(self, raga_id: str, tonic_hz: float = 138.59, tonic_name: str = "C#"):
        self.raga_id = raga_id.lower().replace(" ", "_").replace("-", "_")
        self.tonic_hz = tonic_hz
        self.tonic_name = tonic_name
        self.data: Dict[str, Any] = self._load_raga_data()

        self.name: str = self.data.get("name", raga_id.title())
        self.thaat: str = self.data.get("thaat", "Kalyan")
        self.time: str = self.data.get("time", "Evening")
        self.vadi: str = self.data.get("vadi", "G")
        self.samvadi: str = self.data.get("samvadi", "N")
        self.aroha_raw: List[str] = self.data.get("aroha", ["S", "R", "G", "M", "P", "D", "N", "S'"])
        self.avaroha_raw: List[str] = self.data.get("avaroha", ["S'", "N", "D", "P", "M", "G", "R", "S"])
        self.pakad: List[str] = self.data.get("pakad", [])
        self.motifs: List[List[str]] = self.data.get("motifs", [])

        # Parse swaras
        self.aroha_swaras = [normalize_swara_symbol(s)[0] for s in self.aroha_raw if s]
        self.avaroha_swaras = [normalize_swara_symbol(s)[0] for s in self.avaroha_raw if s]
        self.all_allowed_swaras: Set[str] = set(self.aroha_swaras) | set(self.avaroha_swaras)

        # 12 chromatic swaras
        all_canonical_swaras = {"S", "r", "R", "g", "G", "m", "M", "P", "d", "D", "n", "N"}
        self.forbidden_swaras: Set[str] = all_canonical_swaras - self.all_allowed_swaras

    def _load_raga_data(self) -> Dict[str, Any]:
        """Loads raga definition from the knowledge base or fallback."""
        if self.raga_id in RAGA_KNOWLEDGE_BASE:
            return RAGA_KNOWLEDGE_BASE[self.raga_id]

        # Alias lookup
        for k, v in RAGA_KNOWLEDGE_BASE.items():
            if k.lower() == self.raga_id or v.get("name", "").lower() == self.raga_id:
                return v

        # Fallback to Yaman if unknown
        return RAGA_KNOWLEDGE_BASE.get("yaman", {
            "name": "Yaman",
            "thaat": "Kalyan",
            "time": "Evening",
            "vadi": "G",
            "samvadi": "N",
            "aroha": ["N.", "R", "G", "M", "D", "N", "S'"],
            "avaroha": ["S'", "N", "D", "P", "M", "G", "R", "S"],
            "pakad": ["N.", "R", "G", "M", "P", "R", "G", "R", "S"],
        })

    def swara_to_hz(self, swara_symbol: str) -> float:
        """Converts a swara symbol with optional octave mark to exact frequency in Hz."""
        base_swara, octave = normalize_swara_symbol(swara_symbol)
        semitone = SEMITONE_OFFSETS.get(base_swara, 0)
        # Equal-tempered semitone ratio from Sa
        ratio = (2.0 ** (semitone / 12.0)) * (2.0 ** octave)
        return self.tonic_hz * ratio

    def is_swara_valid(self, swara_symbol: str, is_ascending: Optional[bool] = None) -> bool:
        """Checks if a swara is valid within this raga scale."""
        base_swara, _ = normalize_swara_symbol(swara_symbol)
        if base_swara in self.forbidden_swaras:
            return False
        if is_ascending is True and self.aroha_swaras and base_swara not in self.aroha_swaras:
            return False
        if is_ascending is False and self.avaroha_swaras and base_swara not in self.avaroha_swaras:
            return False
        return base_swara in self.all_allowed_swaras
