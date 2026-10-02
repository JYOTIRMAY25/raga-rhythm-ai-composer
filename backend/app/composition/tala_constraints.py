"""
Tala rhythmic cycle constraints, vibhag divisions, and metric grid modeling.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from backend.app.analysis.tala_knowledge_base import (
    TALA_KNOWLEDGE_BASE,
    TalaDefinition,
    get_tala,
    normalize_tala_lookup_key,
)

EXTENDED_COMPOSITION_TALAS: Dict[str, TalaDefinition] = {
    "tilwada": TalaDefinition(
        name="Tilwada",
        tala_id="tilwada",
        matras=16,
        vibhag_structure=[4, 4, 4, 4],
        sam_position=1,
        khali_positions=[9],
        tali_positions=[1, 5, 13],
        theka_syllables=[
            "Dha", "TirKit", "Dhin", "Dhin",
            "Dha", "Dha", "Tin", "Tin",
            "Ta", "TirKit", "Dhin", "Dhin",
            "Dha", "Dha", "Dhin", "Dhin"
        ],
        description="16-beat cycle commonly used in slow (Vilambit) Khayal compositions."
    ),
    "jhoomra": TalaDefinition(
        name="Jhoomra",
        tala_id="jhoomra",
        matras=14,
        vibhag_structure=[3, 4, 3, 4],
        sam_position=1,
        khali_positions=[8],
        tali_positions=[1, 4, 11],
        theka_syllables=[
            "Dhin", "Dha", "TirKit",
            "Dhin", "Dhin", "DhaGe", "TirKit",
            "Tin", "Ta", "TirKit",
            "Dhin", "Dhin", "DhaGe", "TirKit"
        ],
        description="14-beat classical cycle with syncopated lilt in 4 vibhags (3+4+3+4)."
    ),
    "addha": TalaDefinition(
        name="Addha",
        tala_id="addha",
        aliases=["jatt", "sitarkhani"],
        matras=16,
        vibhag_structure=[4, 4, 4, 4],
        sam_position=1,
        khali_positions=[9],
        tali_positions=[1, 5, 13],
        theka_syllables=[
            "Dha", "Dhin", "Na", "Dha",
            "Dha", "Dhin", "Na", "Dha",
            "Dha", "Tin", "Na", "Ta",
            "Ta", "Dhin", "Na", "Dha"
        ],
        description="16-beat light-classical cycle (also known as Sitarkhani or Addha Trital)."
    ),
}


class TalaConstraints:
    """Encapsulates metric cycle structure, vibhag bounds, bols, and tempo calculations."""

    def __init__(self, tala_id: str, bpm: int = 84):
        self.tala_id = normalize_tala_lookup_key(tala_id)
        self.bpm = max(40, min(240, bpm))
        self.data = self._load_tala_data()

        self.name: str = self.data.name
        self.matras: int = self.data.matras
        self.vibhags: List[int] = self.data.vibhag_structure
        self.vibhag_str: str = "+".join(str(v) for v in self.vibhags)
        self.theka: List[str] = getattr(self.data, "theka_syllables", []) or getattr(self.data, "theka", [])
        self.sam_position: int = getattr(self.data, "sam_position", 1)
        self.khali_positions: List[int] = getattr(self.data, "khali_positions", [])
        self.tali_positions: List[int] = getattr(self.data, "tali_positions", [])

        # Seconds per matra (beat)
        self.seconds_per_matra = 60.0 / self.bpm
        # Seconds per cycle
        self.seconds_per_cycle = self.seconds_per_matra * self.matras

    def _load_tala_data(self) -> TalaDefinition:
        """Loads canonical TalaDefinition from Tala Knowledge Base or extended talas."""
        tala = get_tala(self.tala_id)
        if tala:
            return tala
        if self.tala_id in EXTENDED_COMPOSITION_TALAS:
            return EXTENDED_COMPOSITION_TALAS[self.tala_id]
        for tid, tdef in EXTENDED_COMPOSITION_TALAS.items():
            if tid == self.tala_id or self.tala_id in tdef.aliases:
                return tdef
        # Fallback to Teental
        return get_tala("teental")

    def calculate_cycle_count(self, target_duration_seconds: float) -> int:
        """Calculates total integer Tala cycles needed to approximate target duration."""
        if self.seconds_per_cycle <= 0:
            return 1
        cycles = round(target_duration_seconds / self.seconds_per_cycle)
        return max(1, cycles)

    def get_beat_info(self, matra: int) -> Dict[str, Any]:
        """
        Returns metric metadata for a specific matra (1-indexed) in the cycle:
        - vibhag index (1-indexed)
        - theka bol
        - is_sam, is_khali, is_tali
        """
        m = ((matra - 1) % self.matras) + 1
        bol = self.theka[m - 1] if m <= len(self.theka) else ""

        # Determine vibhag index
        v_idx = 1
        cumulative = 0
        for idx, v_size in enumerate(self.vibhags, start=1):
            cumulative += v_size
            if m <= cumulative:
                v_idx = idx
                break

        is_sam = (m == self.sam_position)
        is_khali = (m in self.khali_positions)
        is_tali = (m in self.tali_positions) and not is_sam

        return {
            "matra": m,
            "vibhag": v_idx,
            "bol": bol,
            "is_sam": is_sam,
            "is_khali": is_khali,
            "is_tali": is_tali,
        }

    @property
    def laya_category(self) -> str:
        """Determines Laya speed category based on BPM."""
        if self.bpm < 60:
            return "Ati-Vilambit"
        if self.bpm < 80:
            return "Vilambit"
        if self.bpm <= 150:
            return "Madhya"
        if self.bpm <= 220:
            return "Drut"
        return "Ati-Drut"
