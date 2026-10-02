"""
Microtonal Shruti and Intonation Modeling for Indian Classical Music.
Provides strongly-typed models, deterministic pitch mappings, raga-specific shruti
knowledge, and contextual intonation adjustments with canonical 12-TET fallback.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

from backend.app.composition.raga_constraints import SEMITONE_OFFSETS, normalize_swara_symbol


# ============================================================================
# Core Mathematical Conversion Utilities
# ============================================================================

def cents_to_ratio(cents: float) -> float:
    """Converts a cents offset to a linear frequency ratio multiplier: 2^(cents / 1200)."""
    return 2.0 ** (cents / 1200.0)


def ratio_to_cents(ratio: float) -> float:
    """Converts a linear frequency ratio to cents: 1200 * log2(ratio)."""
    if ratio <= 0:
        return 0.0
    return 1200.0 * math.log2(ratio)


def cents_to_hz(base_hz: float, cents: float) -> float:
    """Calculates final frequency in Hz given base Hz and cents offset."""
    return base_hz * cents_to_ratio(cents)


def hz_to_cents_offset(base_hz: float, target_hz: float) -> float:
    """Calculates cents offset between base Hz and target Hz."""
    if base_hz <= 0 or target_hz <= 0:
        return 0.0
    return ratio_to_cents(target_hz / base_hz)


# ============================================================================
# Strongly-Typed Models
# ============================================================================

class ShrutiPitch(BaseModel):
    """
    Strongly-typed representation of an intonated swara pitch with explicit
    microtonal cents deviation and contextual modifiers.
    """
    model_config = ConfigDict(extra="ignore")

    swara: str = Field(..., description="Canonical base swara symbol (e.g., 'S', 'r', 'G', 'M')")
    octave: int = Field(default=0, description="Octave offset (-1, 0, 1)")
    base_frequency: float = Field(..., gt=0, description="Canonical 12-TET pitch in Hz")
    cents_offset: float = Field(default=0.0, description="Raga-specific shruti cents deviation from 12-TET")
    context_cents_offset: float = Field(default=0.0, description="Contextual (phrase/direction) cents deviation")
    total_cents_offset: float = Field(default=0.0, description="Sum of raga and contextual cents offsets")
    final_frequency: float = Field(..., gt=0, description="Exact synthesized frequency in Hz")
    raga_id: Optional[str] = Field(None, description="Associated canonical raga ID")
    tuning_mode: str = Field(default="canonical", description="'canonical' (12-TET) or 'raga_aware' (microtonal)")
    source: str = Field(default="canonical_12tet", description="Provenance of intonation assignment")
    ratio_str: Optional[str] = Field(None, description="Classical Just Intonation fraction if applicable")


class IntonationProfile(BaseModel):
    """
    Encapsulates a raga's complete microtonal intonation profile.
    """
    model_config = ConfigDict(extra="ignore")

    raga_id: str
    profile_name: str
    is_raga_specific: bool = Field(default=False)
    swara_cents: Dict[str, float] = Field(default_factory=dict)
    swara_ratios: Dict[str, str] = Field(default_factory=dict)
    description: str = Field(default="")


# ============================================================================
# Documented Microtonal Intonation Knowledge Base
# Documented Just Intonation Shruti intervals for classic Hindustani Ragas
# ============================================================================

DOCUMENTED_RAGA_PROFILES: Dict[str, Dict[str, Any]] = {
    "yaman": {
        "profile_name": "Yaman Just Intonation (Kalyan Thaat)",
        "swara_cents": {
            "S": 0.0,
            "R": 3.91,    # Chatushruti Rishabh (9/8 = 203.91c, +3.91c)
            "G": -13.69,  # Antara Gandhar (5/4 = 386.31c, -13.69c)
            "M": -9.78,   # Tivra Madhyam (45/32 = 590.22c, -9.78c)
            "P": 1.96,    # Pancham (3/2 = 701.96c, +1.96c)
            "D": -15.64,  # Shuddha Dhaivat (5/3 = 884.36c, -15.64c)
            "N": -11.73,  # Kakali Nishad (15/8 = 1088.27c, -11.73c)
        },
        "swara_ratios": {
            "S": "1/1",
            "R": "9/8",
            "G": "5/4",
            "M": "45/32",
            "P": "3/2",
            "D": "5/3",
            "N": "15/8",
        },
        "description": "Pure harmonic thirds and major fifths characteristic of Kalyan thaat.",
    },
    "bhairav": {
        "profile_name": "Bhairav Microtonal Intonation",
        "swara_cents": {
            "S": 0.0,
            "r": 11.73,   # Komal Rishabh (16/15 = 111.73c, +11.73c)
            "G": -13.69,  # Antara Gandhar (5/4 = 386.31c, -13.69c)
            "m": -1.96,   # Shuddha Madhyam (4/3 = 498.04c, -1.96c)
            "P": 1.96,    # Pancham (3/2 = 701.96c, +1.96c)
            "d": 13.69,   # Komal Dhaivat (8/5 = 813.69c, +13.69c)
            "N": -11.73,  # Kakali Nishad (15/8 = 1088.27c, -11.73c)
        },
        "swara_ratios": {
            "S": "1/1",
            "r": "16/15",
            "G": "5/4",
            "m": "4/3",
            "P": "3/2",
            "d": "8/5",
            "N": "15/8",
        },
        "description": "High-seated komal Re and Dha with bright Shuddha Ga and Ni.",
    },
    "todi": {
        "profile_name": "Todi Ati-Komal Intonation",
        "swara_cents": {
            "S": 0.0,
            "r": -9.78,   # Ati-Komal Rishabh (256/243 = 90.22c, -9.78c)
            "g": -5.87,   # Ati-Komal Gandhar (32/27 = 294.13c, -5.87c)
            "M": -9.78,   # Tivra Madhyam (45/32 = 590.22c, -9.78c)
            "P": 1.96,    # Pancham (3/2 = 701.96c, +1.96c)
            "d": -7.82,   # Ati-Komal Dhaivat (128/81 = 792.18c, -7.82c)
            "N": -11.73,  # Kakali Nishad (15/8 = 1088.27c, -11.73c)
        },
        "swara_ratios": {
            "S": "1/1",
            "r": "256/243",
            "g": "32/27",
            "M": "45/32",
            "P": "3/2",
            "d": "128/81",
            "N": "15/8",
        },
        "description": "Characteristic low-slung, grave ati-komal Re, Ga, and Dha with tivra Ma.",
    },
    "darbari_kanhada": {
        "profile_name": "Darbari Kanhada Andolan Intonation",
        "swara_cents": {
            "S": 0.0,
            "R": 3.91,    # Chatushruti Rishabh (9/8 = 203.91c, +3.91c)
            "g": -15.00,  # Deep oscillating Komal Ga (~285c, -15.0c)
            "m": -1.96,   # Shuddha Madhyam (4/3 = 498.04c, -1.96c)
            "P": 1.96,    # Pancham (3/2 = 701.96c, +1.96c)
            "d": -14.00,  # Deep oscillating Komal Dha (~786c, -14.0c)
            "n": -3.91,   # Kaishiki Nishad (16/9 = 996.09c, -3.91c)
        },
        "swara_ratios": {
            "S": "1/1",
            "R": "9/8",
            "g": "andolan_low",
            "m": "4/3",
            "P": "3/2",
            "d": "andolan_low",
            "n": "16/9",
        },
        "description": "Majestic slow microtonal oscillations on Komal Ga and Komal Dha.",
    },
    "malkauns": {
        "profile_name": "Malkauns Just Intonation",
        "swara_cents": {
            "S": 0.0,
            "g": 15.64,   # Sadharana Gandhar (6/5 = 315.64c, +15.64c)
            "m": -1.96,   # Shuddha Madhyam Anchor (4/3 = 498.04c, -1.96c)
            "d": 13.69,   # Komal Dhaivat (8/5 = 813.69c, +13.69c)
            "n": -3.91,   # Kaishiki Nishad (16/9 = 996.09c, -3.91c)
        },
        "swara_ratios": {
            "S": "1/1",
            "g": "6/5",
            "m": "4/3",
            "d": "8/5",
            "n": "16/9",
        },
        "description": "Pancham-varjit meditative symmetry with resonant Ma tonic pivot.",
    },
    "bhoopali": {
        "profile_name": "Bhoopali Just Intonation",
        "swara_cents": {
            "S": 0.0,
            "R": 3.91,    # Chatushruti Rishabh (9/8 = 203.91c, +3.91c)
            "G": -13.69,  # Antara Gandhar (5/4 = 386.31c, -13.69c)
            "P": 1.96,    # Pancham (3/2 = 701.96c, +1.96c)
            "D": -15.64,  # Shuddha Dhaivat (5/3 = 884.36c, -15.64c)
        },
        "swara_ratios": {
            "S": "1/1",
            "R": "9/8",
            "G": "5/4",
            "P": "3/2",
            "D": "5/3",
        },
        "description": "Pure pentatonic major consonance over Sa and Pa anchors.",
    },
    "bhairavi": {
        "profile_name": "Bhairavi Just Intonation",
        "swara_cents": {
            "S": 0.0,
            "r": 11.73,   # Komal Rishabh (16/15 = 111.73c, +11.73c)
            "g": 15.64,   # Komal Gandhar (6/5 = 315.64c, +15.64c)
            "m": -1.96,   # Shuddha Madhyam (4/3 = 498.04c, -1.96c)
            "P": 1.96,    # Pancham (3/2 = 701.96c, +1.96c)
            "d": 13.69,   # Komal Dhaivat (8/5 = 813.69c, +13.69c)
            "n": -3.91,   # Komal Nishad (16/9 = 996.09c, -3.91c)
        },
        "swara_ratios": {
            "S": "1/1",
            "r": "16/15",
            "g": "6/5",
            "m": "4/3",
            "P": "3/2",
            "d": "8/5",
            "n": "16/9",
        },
        "description": "Universal all-komal devotional scale with pure fourths and fifths.",
    },
    "kafi": {
        "profile_name": "Kafi Intonation",
        "swara_cents": {
            "S": 0.0,
            "R": -17.60,  # Trishruti Rishabh (10/9 = 182.40c, -17.60c)
            "g": 15.64,   # Komal Gandhar (6/5 = 315.64c, +15.64c)
            "m": -1.96,   # Shuddha Madhyam (4/3 = 498.04c, -1.96c)
            "P": 1.96,    # Pancham (3/2 = 701.96c, +1.96c)
            "D": -15.64,  # Shuddha Dhaivat (5/3 = 884.36c, -15.64c)
            "n": 17.60,   # Kaishiki Nishad (9/5 = 1017.60c, +17.60c)
        },
        "swara_ratios": {
            "S": "1/1",
            "R": "10/9",
            "g": "6/5",
            "m": "4/3",
            "P": "3/2",
            "D": "5/3",
            "n": "9/5",
        },
        "description": "Minor-tone Rishabh and expressive high Komal Nishad.",
    },
}

# Aliases mapping
RAGA_PROFILE_ALIASES: Dict[str, str] = {
    "yaman_kalyan": "yaman",
    "kalyan": "yaman",
    "darbari": "darbari_kanhada",
    "bhupali": "bhoopali",
    "shuddha_kalyan": "yaman",
}


# ============================================================================
# ShrutiMapper & Intonation Controller
# ============================================================================

class ShrutiMapper:
    """
    Raga-aware and context-sensitive microtonal intonation mapper.
    Always maintains guaranteed canonical 12-TET fallback when tuning_mode='canonical'
    or when a raga has no explicit microtonal knowledge assignment.
    """

    @classmethod
    def normalize_raga_key(cls, raga_id: Optional[str]) -> str:
        if not raga_id:
            return ""
        clean = raga_id.lower().strip().replace(" ", "_").replace("-", "_")
        return RAGA_PROFILE_ALIASES.get(clean, clean)

    @classmethod
    def get_profile(cls, raga_id: Optional[str], tuning_mode: str = "canonical") -> IntonationProfile:
        """
        Retrieves the intonation profile for a raga. If tuning_mode is 'canonical' or the
        raga is unmapped, returns a zero-offset canonical fallback profile.
        """
        clean_key = cls.normalize_raga_key(raga_id)

        if tuning_mode != "raga_aware" or clean_key not in DOCUMENTED_RAGA_PROFILES:
            return IntonationProfile(
                raga_id=clean_key or "default",
                profile_name="Canonical 12-TET Standard",
                is_raga_specific=False,
                swara_cents={},
                swara_ratios={},
                description="Standard equal temperament / canonical mathematical scale.",
            )

        data = DOCUMENTED_RAGA_PROFILES[clean_key]
        return IntonationProfile(
            raga_id=clean_key,
            profile_name=data["profile_name"],
            is_raga_specific=True,
            swara_cents=data.get("swara_cents", {}),
            swara_ratios=data.get("swara_ratios", {}),
            description=data.get("description", ""),
        )

    @classmethod
    def compute_context_offset(
        cls,
        base_swara: str,
        prev_swara: Optional[str] = None,
        next_swara: Optional[str] = None,
        is_ascending: Optional[bool] = None,
        is_cadence: bool = False,
        ornament: Optional[str] = None,
    ) -> float:
        """
        Calculates subtle contextual microtonal adjustments (in cents):
        - Ascending leading movement (e.g. N -> S or G -> M): +3 cents brightness
        - Descending relaxation (e.g. R -> S or D -> P): -3 cents soft settling
        - Cadential resolution to Sam/Sa: exact 0 cents stability
        """
        if is_cadence or base_swara == "S":
            return 0.0

        ctx_cents = 0.0

        # Melodic direction inflection
        if is_ascending is True:
            ctx_cents += 2.5
        elif is_ascending is False:
            ctx_cents -= 2.5

        # Leading tone attraction toward Sa or Pa
        if next_swara == "S" and base_swara in {"N", "n"}:
            ctx_cents += 2.0  # slight upward pull to Shadja
        elif next_swara == "S" and base_swara in {"R", "r"}:
            ctx_cents -= 2.0  # downward settling onto Shadja
        elif next_swara == "P" and base_swara in {"M", "m"}:
            ctx_cents += 1.5

        # Bound contextual inflection to max +/- 5.0 cents to prevent runaway deviation
        return max(-5.0, min(5.0, ctx_cents))

    @classmethod
    def map_pitch(
        cls,
        swara_symbol: str,
        tonic_hz: float,
        raga_id: Optional[str] = None,
        tuning_mode: str = "canonical",
        prev_swara: Optional[str] = None,
        next_swara: Optional[str] = None,
        is_ascending: Optional[bool] = None,
        is_cadence: bool = False,
        ornament: Optional[str] = None,
    ) -> ShrutiPitch:
        """
        Maps a symbolic swara and tonic into a strongly-typed ShrutiPitch.
        Deterministic: Same arguments always return identical frequencies.
        """
        clean_swara, octave = normalize_swara_symbol(swara_symbol)
        semitone = SEMITONE_OFFSETS.get(clean_swara, 0)

        # 1. Base Canonical Frequency (12-TET)
        base_hz = tonic_hz * (2.0 ** ((semitone + 12 * octave) / 12.0))

        # 2. Raga-Aware Shruti Tuning
        profile = cls.get_profile(raga_id, tuning_mode=tuning_mode)
        raga_cents = profile.swara_cents.get(clean_swara, 0.0) if profile.is_raga_specific else 0.0
        ratio_str = profile.swara_ratios.get(clean_swara, None) if profile.is_raga_specific else None

        # 3. Contextual Adjustment
        context_cents = 0.0
        if tuning_mode == "raga_aware":
            context_cents = cls.compute_context_offset(
                base_swara=clean_swara,
                prev_swara=prev_swara,
                next_swara=next_swara,
                is_ascending=is_ascending,
                is_cadence=is_cadence,
                ornament=ornament,
            )

        total_cents = raga_cents + context_cents
        final_hz = cents_to_hz(base_hz, total_cents)

        source = (
            f"raga_profile:{profile.raga_id}"
            if profile.is_raga_specific
            else "canonical_12tet"
        )

        return ShrutiPitch(
            swara=clean_swara,
            octave=octave,
            base_frequency=base_hz,
            cents_offset=raga_cents,
            context_cents_offset=context_cents,
            total_cents_offset=total_cents,
            final_frequency=final_hz,
            raga_id=profile.raga_id,
            tuning_mode=tuning_mode,
            source=source,
            ratio_str=ratio_str,
        )


shruti_mapper = ShrutiMapper()
