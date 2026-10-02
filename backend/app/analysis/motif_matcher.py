"""
Melodic Motif (Pakad / Chalan) Parser and Matcher for RagaRhythm AI.

Provides:
1. Robust parsing and normalization of 2,832+ manual melodic phrase annotations (.mphrases-manual.txt).
2. Structured motif representation (tokens, n-grams, collapsed sequences).
3. Melodic motif similarity and evidence extraction matching against SwaraAnalyzer outputs.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

ALL_SWARA_SYMBOLS = ["S", "r", "R", "g", "G", "m", "M", "P", "d", "D", "n", "N"]
VALID_SWARA_SET = set(ALL_SWARA_SYMBOLS)


# ============================================================================
# Domain Models
# ============================================================================

class ParsedMelodicMotif(BaseModel):
    """Structured representation of an individual melodic phrase/pakad."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    raw_text: str = Field(..., description="Original raw phrase string")
    swaras: List[str] = Field(..., description="Canonical sequence of swara symbols")
    length: int = Field(..., description="Number of swaras in the motif")
    bigrams: List[Tuple[str, str]] = Field(default_factory=list, description="Ordered 2-gram swara transitions")
    trigrams: List[Tuple[str, str, str]] = Field(default_factory=list, description="Ordered 3-gram swara transitions")
    is_valid: bool = Field(default=True, description="Whether the phrase contains only valid swara symbols")

    @property
    def display_str(self) -> str:
        return " ".join(self.swaras)

    @property
    def compact_str(self) -> str:
        return "".join(self.swaras)


class MotifMatchDetail(BaseModel):
    """Detailed diagnostics for an individual motif comparison."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    motif_swaras: List[str]
    motif_str: str
    match_type: str = Field(..., description="e.g. 'exact_contiguous', 'collapsed_contiguous', 'fuzzy_subsequence', 'none'")
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    matched_subsequence: Optional[str] = None
    position_in_stream: Optional[int] = None


class MotifMatchEvidence(BaseModel):
    """Complete inspectable motif match evidence for a candidate raga."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    matched_motifs: List[str] = Field(default_factory=list, description="List of recognized pakad strings")
    match_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Composite melodic motif similarity [0.0, 1.0]")
    coverage_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="Ratio of raga pakads matched [0.0, 1.0]")
    longest_match_len: int = Field(default=0, description="Longest contiguous matched motif length")
    best_motif: Optional[str] = Field(default=None, description="Highest scoring matched pakad phrase")
    details: List[MotifMatchDetail] = Field(default_factory=list, description="Per-motif matching details")


# ============================================================================
# Reusable Melodic Phrase Parser
# ============================================================================

class MelodicPhraseParser:
    """
    Type-safe, robust parser for Hindustani melodic phrases and pakad motifs.
    
    Handles:
    - Saraga .mphrases-manual.txt formats (e.g. 'NrS', 'rNdP', 'DNrGrND', 'gRm', 'Rns')
    - Space-separated and hyphenated swara lists (e.g. 'N R G', 'M-D-N-S')
    - Lowercase 's' normalization to canonical 'S'
    - Stripping invalid non-swara characters (punctuation, numbers, whitespace)
    """

    @classmethod
    def parse_motif(cls, phrase_str: Union[str, Sequence[str]]) -> ParsedMelodicMotif:
        """
        Parses a raw phrase string or sequence into a structured ParsedMelodicMotif.
        """
        if isinstance(phrase_str, (list, tuple)):
            raw = " ".join(str(s) for s in phrase_str)
            tokens: List[str] = []
            for item in phrase_str:
                s_item = str(item).strip()
                if not s_item:
                    continue
                # If item has multiple characters, parse individual characters
                if len(s_item) > 1 and all(c in VALID_SWARA_SET or c == 's' for c in s_item):
                    tokens.extend([cls._normalize_char(c) for c in s_item])
                else:
                    norm = cls._normalize_swara(s_item)
                    if norm:
                        tokens.append(norm)
        elif isinstance(phrase_str, str):
            raw = phrase_str.strip()
            tokens = cls._parse_string_tokens(raw)
        else:
            raw = str(phrase_str)
            tokens = []

        # Validate tokens
        valid_tokens = [t for t in tokens if t in VALID_SWARA_SET]
        is_valid = len(valid_tokens) == len(tokens) and len(tokens) > 0

        # Build bigrams and trigrams
        bigrams = [(valid_tokens[i], valid_tokens[i + 1]) for i in range(len(valid_tokens) - 1)]
        trigrams = [(valid_tokens[i], valid_tokens[i + 1], valid_tokens[i + 2]) for i in range(len(valid_tokens) - 2)]

        return ParsedMelodicMotif(
            raw_text=raw,
            swaras=valid_tokens,
            length=len(valid_tokens),
            bigrams=bigrams,
            trigrams=trigrams,
            is_valid=is_valid,
        )

    @classmethod
    def _normalize_char(cls, char: str) -> str:
        """Normalizes a single character; specifically 's' -> 'S' for Shadja."""
        if char == "s":
            return "S"
        return char

    @classmethod
    def _normalize_swara(cls, swara: str) -> Optional[str]:
        """Normalizes word/symbol swara tokens (e.g. 'Sa' -> 'S', 're' -> 'r', 'Re' -> 'R')."""
        s = swara.strip()
        if not s:
            return None
        if s == "s":
            return "S"
        if s in VALID_SWARA_SET:
            return s
        
        # Word mappings
        word_map = {
            "sa": "S", "shadja": "S",
            "komal re": "r", "komal rishabh": "r", "komal_re": "r", "re_komal": "r",
            "shuddha re": "R", "shuddha rishabh": "R", "re": "R", "rishabh": "R",
            "komal ga": "g", "komal gandhar": "g", "komal_ga": "g", "ga_komal": "g",
            "shuddha ga": "G", "shuddha gandhar": "G", "ga": "G", "gandhar": "G",
            "shuddha ma": "m", "shuddha madhyam": "m", "ma": "m", "madhyam": "m",
            "tivra ma": "M", "tivra madhyam": "M", "tivra_ma": "M", "ma_tivra": "M",
            "pa": "P", "pancham": "P",
            "komal dha": "d", "komal dhaivat": "d", "komal_dha": "d", "dha_komal": "d",
            "shuddha dha": "D", "shuddha dhaivat": "D", "dha": "D", "dhaivat": "D",
            "komal ni": "n", "komal nishad": "n", "komal_ni": "n", "ni_komal": "n",
            "shuddha ni": "N", "shuddha nishad": "N", "ni": "N", "nishad": "N",
        }
        low = s.lower()
        if low in word_map:
            return word_map[low]

        return None

    @classmethod
    def _parse_string_tokens(cls, raw: str) -> List[str]:
        """Parses a raw phrase string into a list of swara tokens."""
        if not raw:
            return []

        # If whitespace separated
        if " " in raw or "," in raw or "-" in raw or "_" in raw:
            parts = re.split(r"[\s,\-_]+", raw)
            tokens: List[str] = []
            for p in parts:
                p_clean = p.strip()
                if not p_clean:
                    continue
                # If part is single or known token
                if p_clean in VALID_SWARA_SET or p_clean == "s":
                    tokens.append(cls._normalize_char(p_clean))
                else:
                    # Check if composite word or multiple characters
                    norm = cls._normalize_swara(p_clean)
                    if norm:
                        tokens.append(norm)
                    else:
                        # Character by character
                        for c in p_clean:
                            if c in VALID_SWARA_SET or c == "s":
                                tokens.append(cls._normalize_char(c))
            return tokens

        # Contiguous single-character format (e.g. 'NrS', 'mPgm', 'DNrGrND')
        tokens = []
        for c in raw:
            if c in VALID_SWARA_SET or c == "s":
                tokens.append(cls._normalize_char(c))
        return tokens


# ============================================================================
# Melodic Motif Matcher
# ============================================================================

class MelodicMotifMatcher:
    """
    Melodic Motif & Pakad Sequence Matching Engine.
    
    Matches candidate raga pakad motifs against observed swara performance data.
    Provides robust multi-tiered matching:
    1. Exact contiguous substring matching in collapsed and raw swara streams.
    2. N-gram transition graph matching.
    3. Sliding-window Levenshtein similarity on melodic segments.
    """

    @classmethod
    def extract_stream_symbols(
        cls,
        segments_or_symbols: Sequence[Any],
    ) -> Tuple[List[str], List[str]]:
        """
        Extracts both full symbol stream and collapsed stream (consecutive duplicates merged).
        """
        raw_symbols: List[str] = []
        for item in segments_or_symbols:
            if hasattr(item, "symbol"):
                sym = str(item.symbol)
            elif isinstance(item, dict):
                sym = str(item.get("symbol", ""))
            elif isinstance(item, str):
                sym = item
            else:
                sym = ""

            if sym and sym in VALID_SWARA_SET:
                raw_symbols.append(sym)

        # Build collapsed stream
        collapsed: List[str] = []
        for s in raw_symbols:
            if not collapsed or s != collapsed[-1]:
                collapsed.append(s)

        return raw_symbols, collapsed

    @classmethod
    def match_raga_motifs(
        cls,
        candidate_pakad_motifs: Sequence[Union[List[str], str, ParsedMelodicMotif]],
        observed_segments_or_symbols: Sequence[Any],
        min_motif_len: int = 2,
    ) -> MotifMatchEvidence:
        """
        Evaluates candidate raga pakad motifs against observed swara performance stream.
        
        Args:
            candidate_pakad_motifs: List of pakad motifs for a candidate raga.
            observed_segments_or_symbols: Output from SwaraAnalyzer (segments or symbols).
            min_motif_len: Minimum swara length required for motif consideration.
            
        Returns:
            MotifMatchEvidence containing score, matched motifs, and decomposed details.
        """
        if not candidate_pakad_motifs or not observed_segments_or_symbols:
            return MotifMatchEvidence(
                matched_motifs=[],
                match_score=0.0,
                coverage_ratio=0.0,
                longest_match_len=0,
                best_motif=None,
                details=[],
            )

        raw_stream, collapsed_stream = cls.extract_stream_symbols(observed_segments_or_symbols)
        if not collapsed_stream:
            return MotifMatchEvidence(
                matched_motifs=[],
                match_score=0.0,
                coverage_ratio=0.0,
                longest_match_len=0,
                best_motif=None,
                details=[],
            )

        raw_str = " ".join(raw_stream)
        collapsed_str = " ".join(collapsed_stream)
        raw_compact = "".join(raw_stream)
        collapsed_compact = "".join(collapsed_stream)

        parsed_motifs: List[ParsedMelodicMotif] = []
        for m in candidate_pakad_motifs:
            if isinstance(m, ParsedMelodicMotif):
                pm = m
            else:
                pm = MelodicPhraseParser.parse_motif(m)
            if pm.is_valid and pm.length >= min_motif_len:
                parsed_motifs.append(pm)

        if not parsed_motifs:
            return MotifMatchEvidence(
                matched_motifs=[],
                match_score=0.0,
                coverage_ratio=0.0,
                longest_match_len=0,
                best_motif=None,
                details=[],
            )

        details: List[MotifMatchDetail] = []
        matched_motifs: List[str] = []
        motif_scores: List[float] = []

        for pm in parsed_motifs:
            motif_str = pm.display_str
            motif_compact = pm.compact_str
            m_len = pm.length

            # 1. Exact contiguous match in collapsed stream (highest fidelity)
            if motif_compact in collapsed_compact or motif_str in collapsed_str:
                pos = collapsed_compact.find(motif_compact)
                detail = MotifMatchDetail(
                    motif_swaras=pm.swaras,
                    motif_str=motif_str,
                    match_type="exact_collapsed_contiguous",
                    similarity_score=1.0,
                    matched_subsequence=motif_str,
                    position_in_stream=pos,
                )
                details.append(detail)
                matched_motifs.append(motif_str)
                motif_scores.append(1.0)
                continue

            # 2. Exact contiguous match in raw stream
            if motif_compact in raw_compact or motif_str in raw_str:
                pos = raw_compact.find(motif_compact)
                detail = MotifMatchDetail(
                    motif_swaras=pm.swaras,
                    motif_str=motif_str,
                    match_type="exact_raw_contiguous",
                    similarity_score=0.95,
                    matched_subsequence=motif_str,
                    position_in_stream=pos,
                )
                details.append(detail)
                matched_motifs.append(motif_str)
                motif_scores.append(0.95)
                continue

            # 3. N-gram bigram / trigram coverage matching
            bg_matches = sum(1 for bg in pm.bigrams if f"{bg[0]} {bg[1]}" in collapsed_str)
            bg_ratio = bg_matches / len(pm.bigrams) if pm.bigrams else 0.0

            tg_matches = sum(1 for tg in pm.trigrams if f"{tg[0]} {tg[1]} {tg[2]}" in collapsed_str)
            tg_ratio = tg_matches / len(pm.trigrams) if pm.trigrams else 0.0

            # 4. Sliding-window fuzzy edit distance on collapsed stream
            best_sim, best_pos, best_sub = cls._sliding_window_similarity(pm.swaras, collapsed_stream)

            # Combine fuzzy signals
            composite_sub_score = max(
                best_sim,
                (0.6 * tg_ratio + 0.4 * bg_ratio) if tg_ratio > 0 else (0.7 * bg_ratio)
            )

            if composite_sub_score >= 0.70:
                match_type = "fuzzy_subsequence_strong" if composite_sub_score >= 0.85 else "fuzzy_subsequence"
                detail = MotifMatchDetail(
                    motif_swaras=pm.swaras,
                    motif_str=motif_str,
                    match_type=match_type,
                    similarity_score=round(composite_sub_score, 3),
                    matched_subsequence=best_sub,
                    position_in_stream=best_pos,
                )
                details.append(detail)
                if composite_sub_score >= 0.80:
                    matched_motifs.append(motif_str)
                motif_scores.append(composite_sub_score)
            else:
                detail = MotifMatchDetail(
                    motif_swaras=pm.swaras,
                    motif_str=motif_str,
                    match_type="none",
                    similarity_score=round(composite_sub_score, 3),
                    matched_subsequence=best_sub,
                    position_in_stream=best_pos,
                )
                details.append(detail)
                motif_scores.append(composite_sub_score * 0.5)

        # Aggregate overall composite score
        if not motif_scores:
            return MotifMatchEvidence(
                matched_motifs=[],
                match_score=0.0,
                coverage_ratio=0.0,
                longest_match_len=0,
                best_motif=None,
                details=details,
            )

        # Mean of top matched motifs with bonus for multiple distinct matches
        sorted_scores = sorted(motif_scores, reverse=True)
        top_k = sorted_scores[:min(len(sorted_scores), 3)]
        base_score = float(np.mean(top_k)) if top_k else 0.0

        matched_count = len([s for s in motif_scores if s >= 0.70])
        coverage_ratio = float(matched_count / len(parsed_motifs))

        # Diversity bonus up to +15% if multiple motifs match strongly
        diversity_bonus = min(0.15, matched_count * 0.05) if base_score > 0.4 else 0.0
        final_score = float(np.clip(base_score + diversity_bonus, 0.0, 1.0))

        # Longest match length
        matched_lens = [len(d.motif_swaras) for d in details if d.similarity_score >= 0.75]
        longest_len = max(matched_lens) if matched_lens else 0

        # Best motif
        best_detail = max(details, key=lambda d: d.similarity_score, default=None)
        best_motif = best_detail.motif_str if best_detail and best_detail.similarity_score >= 0.70 else None

        return MotifMatchEvidence(
            matched_motifs=matched_motifs,
            match_score=round(final_score, 3),
            coverage_ratio=round(coverage_ratio, 3),
            longest_match_len=longest_len,
            best_motif=best_motif,
            details=details,
        )

    @classmethod
    def _sliding_window_similarity(
        cls,
        target_swaras: List[str],
        stream_swaras: List[str],
    ) -> Tuple[float, Optional[int], Optional[str]]:
        """
        Slides window of length L = len(target_swaras) over stream and computes normalized Levenshtein similarity.
        """
        m = len(target_swaras)
        n = len(stream_swaras)
        if m == 0 or n == 0:
            return 0.0, None, None

        if n < m:
            sim = cls.compute_sequence_similarity(target_swaras, stream_swaras)
            return sim, 0, " ".join(stream_swaras)

        best_sim = 0.0
        best_pos = None
        best_sub = None

        # Check window sizes m - 1, m, m + 1
        for w_len in (m - 1, m, m + 1):
            if w_len < 1 or w_len > n:
                continue
            for i in range(0, n - w_len + 1):
                window = stream_swaras[i : i + w_len]
                sim = cls.compute_sequence_similarity(target_swaras, window)
                if sim > best_sim:
                    best_sim = sim
                    best_pos = i
                    best_sub = " ".join(window)
                    if best_sim >= 0.99:
                        return 1.0, best_pos, best_sub

        return best_sim, best_pos, best_sub

    @classmethod
    def compute_sequence_similarity(
        cls,
        seq_a: Sequence[str],
        seq_b: Sequence[str],
    ) -> float:
        """
        Computes normalized Levenshtein distance on swara symbol sequences:
        similarity = 1.0 - (edit_distance / max(len_a, len_b))
        """
        len_a, len_b = len(seq_a), len(seq_b)
        if len_a == 0 and len_b == 0:
            return 1.0
        if len_a == 0 or len_b == 0:
            return 0.0

        # Dynamic programming Levenshtein table
        dp = [[0] * (len_b + 1) for _ in range(len_a + 1)]
        for i in range(len_a + 1):
            dp[i][0] = i
        for j in range(len_b + 1):
            dp[0][j] = j

        for i in range(1, len_a + 1):
            for j in range(1, len_b + 1):
                if seq_a[i - 1] == seq_b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(
                        dp[i - 1][j],     # deletion
                        dp[i][j - 1],     # insertion
                        dp[i - 1][j - 1], # substitution
                    )

        dist = dp[len_a][len_b]
        max_len = max(len_a, len_b)
        sim = max(0.0, 1.0 - (dist / max_len))
        return float(sim)
