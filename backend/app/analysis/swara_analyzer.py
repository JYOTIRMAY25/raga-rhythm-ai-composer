"""
SwaraAnalyzer for RagaRhythm AI.

Converts continuous fundamental-frequency (F0) pitch contours into an Indian
classical music swara representation (12-swara pitch classes with Komal/Shuddha/Tivra
variants and Saptak registers) relative to the estimated Sa tonic.

Provides frame-level mapping, hysteresis anti-flicker smoothing, event-level
swara segmentation, transition bigrams, pitch-class distributions (PCD), and
melodic ornament (meend, gamak/andolan) detection.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from backend.app.analysis.pitch_extractor import PitchExtractionResult
from backend.app.analysis.tonic_estimator import TonicEstimationResult

logger = logging.getLogger(__name__)

# Canonical 12 Swara Definitions (in semitone order from Sa)
SWARA_DEFINITIONS = [
    {"index": 0, "name": "Sa", "symbol": "S", "variant": "shuddha", "cents": 0.0},
    {"index": 1, "name": "Re", "symbol": "r", "variant": "komal", "cents": 100.0},
    {"index": 2, "name": "Re", "symbol": "R", "variant": "shuddha", "cents": 200.0},
    {"index": 3, "name": "Ga", "symbol": "g", "variant": "komal", "cents": 300.0},
    {"index": 4, "name": "Ga", "symbol": "G", "variant": "shuddha", "cents": 400.0},
    {"index": 5, "name": "Ma", "symbol": "m", "variant": "shuddha", "cents": 500.0},
    {"index": 6, "name": "Ma", "symbol": "M", "variant": "tivra", "cents": 600.0},
    {"index": 7, "name": "Pa", "symbol": "P", "variant": "shuddha", "cents": 700.0},
    {"index": 8, "name": "Dha", "symbol": "d", "variant": "komal", "cents": 800.0},
    {"index": 9, "name": "Dha", "symbol": "D", "variant": "shuddha", "cents": 900.0},
    {"index": 10, "name": "Ni", "symbol": "n", "variant": "komal", "cents": 1000.0},
    {"index": 11, "name": "Ni", "symbol": "N", "variant": "shuddha", "cents": 1100.0},
]


class SwaraSegment(BaseModel):
    """Structured segment representing a sustained or connected swara event."""
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    swara: str = Field(..., description="Swara name (Sa, Re, Ga, Ma, Pa, Dha, Ni, NONE)")
    symbol: str = Field(..., description="Canonical symbol (S, r, R, g, G, m, M, P, d, D, n, N, NONE)")
    variant: str = Field(..., description="Variant (shuddha, komal, tivra, NONE)")
    saptak_register: str = Field(default="madhya", alias="register", description="Saptak register (mandra, madhya, taar, NONE)")
    start_time_seconds: float = Field(..., description="Start timestamp in seconds")
    end_time_seconds: float = Field(..., description="End timestamp in seconds")
    duration_seconds: float = Field(..., description="Duration in seconds")
    mean_frequency_hz: float = Field(..., description="Mean fundamental frequency in Hz")
    mean_cents_deviation: float = Field(..., description="Mean cents deviation from canonical swara center")
    mean_confidence: float = Field(..., description="Mean voicing/swara confidence [0.0, 1.0]")
    movement_type: str = Field(default="steady", description="Movement pattern: steady, ascending, descending, meend, oscillation")

    @property
    def register(self) -> str:
        return self.saptak_register



class SwaraAnalysisResult(BaseModel):
    """Complete structured result of swara analysis for downstream Raga/Tala engines."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    timestamps_seconds: np.ndarray = Field(..., description="Timestamps for every frame")
    frequencies_hz: np.ndarray = Field(..., description="Frequencies in Hz")
    swaras: List[str] = Field(..., description="Swara names per frame (Sa, Re, ..., NONE)")
    symbols: List[str] = Field(..., description="Canonical symbols per frame (S, r, R, ..., NONE)")
    variants: List[str] = Field(..., description="Variant per frame (shuddha, komal, tivra, NONE)")
    registers: List[str] = Field(..., description="Saptak register per frame (mandra, madhya, taar, NONE)")
    cents_from_tonic: np.ndarray = Field(..., description="Cents relative to estimated tonic Sa")
    cents_from_swara_center: np.ndarray = Field(..., description="Microtonal deviation from nearest swara center in cents [-50, +50]")
    confidence_values: np.ndarray = Field(..., description="Confidence scores per frame [0.0, 1.0]")
    
    segments: List[SwaraSegment] = Field(default_factory=list, description="Contiguous swara event segments")
    pitch_class_distribution: Dict[str, float] = Field(default_factory=dict, description="12-tone Pitch Class Distribution (PCD) normalized sum")
    dominant_swaras: List[Tuple[str, float]] = Field(default_factory=list, description="Ranked dominant swaras by voiced duration")
    transitions: List[Tuple[str, str]] = Field(default_factory=list, description="Ordered sequence of swara transitions (bigrams)")
    ornaments: List[Dict[str, Any]] = Field(default_factory=list, description="Detected melodic ornaments (meend, gamak, andolan)")
    
    swara_coverage_percentage: float = Field(default=0.0, description="Percentage of frames with a recognized swara")
    unvoiced_percentage: float = Field(default=0.0, description="Percentage of unvoiced/silent frames")
    tonic_hz: float = Field(default=0.0, description="Tonic Sa frequency used in analysis")
    method: str = Field(default="hysteresis_swara_pcd", description="Swara analysis algorithm used")
    diagnostics: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic metrics")

    def to_summary_dict(self) -> Dict[str, Any]:
        """Returns JSON-serializable summary metadata."""
        return {
            "tonic_hz": round(self.tonic_hz, 2),
            "total_frames": len(self.timestamps_seconds),
            "swara_coverage_percentage": round(self.swara_coverage_percentage, 2),
            "unvoiced_percentage": round(self.unvoiced_percentage, 2),
            "dominant_swaras": [(s, round(w, 3)) for s, w in self.dominant_swaras[:5]],
            "total_segments": len(self.segments),
            "total_transitions": len(self.transitions),
            "total_ornaments": len(self.ornaments),
            "pitch_class_distribution": {k: round(v, 4) for k, v in self.pitch_class_distribution.items()},
            "method": self.method,
            "diagnostics": self.diagnostics,
        }


class SwaraAnalyzer:
    """
    Indian Classical Music Swara Analyzer.
    
    Converts continuous pitch tracks into 12-swara pitch classes with:
    - Microtonal cent tracking relative to Sa tonic.
    - Hysteresis anti-flicker smoothing to prevent frame-by-frame chatter.
    - Saptak octave register classification (Mandra, Madhya, Taar).
    - Event-level segment grouping and transition matrix extraction.
    - Ornament detection (meend glissandi and gamak/andolan oscillations).
    - Pitch Class Distribution (PCD) calculation for Raga detection.
    """

    DEFAULT_AMBIGUITY_THRESHOLD_CENTS = 45.0
    DEFAULT_MIN_SEGMENT_FRAMES = 3
    DEFAULT_MIN_VOICED_CONFIDENCE = 0.50

    def __init__(
        self,
        ambiguity_threshold_cents: float = DEFAULT_AMBIGUITY_THRESHOLD_CENTS,
        min_segment_frames: int = DEFAULT_MIN_SEGMENT_FRAMES,
        min_voiced_confidence: float = DEFAULT_MIN_VOICED_CONFIDENCE,
        hysteresis_frames: int = 2,
    ):
        self.ambiguity_threshold_cents = ambiguity_threshold_cents
        self.min_segment_frames = min_segment_frames
        self.min_voiced_confidence = min_voiced_confidence
        self.hysteresis_frames = hysteresis_frames

    def analyze(
        self,
        pitch_result: Union[PitchExtractionResult, Dict[str, Any]],
        tonic_input: Union[TonicEstimationResult, float, Dict[str, Any]],
    ) -> SwaraAnalysisResult:
        """
        Main analysis entrypoint: maps pitch frames to swaras and extracts segments.
        
        Args:
            pitch_result: PitchExtractionResult instance or dictionary.
            tonic_input: TonicEstimationResult instance, float tonic in Hz, or dict.
            
        Returns:
            SwaraAnalysisResult payload.
        """
        # 1. Parse and validate tonic
        tonic_hz = 0.0
        tonic_confidence = 1.0
        if isinstance(tonic_input, TonicEstimationResult):
            tonic_hz = float(tonic_input.tonic_hz)
            tonic_confidence = float(tonic_input.confidence)
        elif isinstance(tonic_input, (int, float)):
            tonic_hz = float(tonic_input)
        elif isinstance(tonic_input, dict):
            tonic_hz = float(tonic_input.get("tonic_hz", 0.0))
            tonic_confidence = float(tonic_input.get("confidence", 1.0))
        else:
            raise ValueError(f"Unsupported tonic_input type: {type(tonic_input)}")

        # 2. Parse pitch extraction result
        if isinstance(pitch_result, PitchExtractionResult):
            timestamps = np.array(pitch_result.timestamps_seconds, dtype=np.float32)
            frequencies = np.array(pitch_result.frequencies_hz, dtype=np.float32)
            voiced_mask = np.array(pitch_result.voiced_mask, dtype=bool)
            confidences = np.array(pitch_result.confidence_values, dtype=np.float32)
        elif isinstance(pitch_result, dict):
            timestamps = np.array(pitch_result["timestamps_seconds"], dtype=np.float32)
            frequencies = np.array(pitch_result["frequencies_hz"], dtype=np.float32)
            voiced_mask = np.array(pitch_result.get("voiced_mask", frequencies > 0.0), dtype=bool)
            confidences = np.array(pitch_result.get("confidence_values", np.ones_like(frequencies)), dtype=np.float32)
        else:
            raise ValueError(f"Unsupported pitch_result type: {type(pitch_result)}")

        num_frames = len(timestamps)
        if num_frames == 0:
            return self._empty_result(tonic_hz)

        # Sanitize any NaN/Inf entries
        frequencies = np.nan_to_num(frequencies, nan=0.0, posinf=0.0, neginf=0.0)
        confidences = np.nan_to_num(confidences, nan=0.0, posinf=0.0, neginf=0.0)

        # 3. If tonic is invalid (<= 0 or non-finite), return safe unvoiced/NONE frames
        if tonic_hz <= 0.0 or not np.isfinite(tonic_hz) or tonic_confidence <= 0.0:
            logger.warning("Invalid or zero tonic frequency provided. Returning NONE swaras.")
            return self._fallback_unvoiced_result(timestamps, frequencies, tonic_hz)

        # 4. Frame-by-frame Swara mapping
        raw_swaras: List[str] = []
        raw_symbols: List[str] = []
        raw_variants: List[str] = []
        raw_registers: List[str] = []
        cents_from_tonic = np.zeros(num_frames, dtype=np.float32)
        cents_from_swara_center = np.zeros(num_frames, dtype=np.float32)

        for i in range(num_frames):
            f = frequencies[i]
            is_voiced = voiced_mask[i] and (f > 0.0) and (confidences[i] >= self.min_voiced_confidence)

            if not is_voiced:
                raw_swaras.append("NONE")
                raw_symbols.append("NONE")
                raw_variants.append("NONE")
                raw_registers.append("NONE")
                continue

            # Compute continuous cents relative to Sa tonic
            total_cents = 1200.0 * np.log2(f / tonic_hz)
            cents_from_tonic[i] = total_cents

            # Octave / Saptak calculation
            octave_idx = int(np.floor(total_cents / 1200.0))
            if octave_idx < 0:
                reg = "mandra"
            elif octave_idx == 0:
                reg = "madhya"
            else:
                reg = "taar"

            # 12-Tone Pitch Class
            octave_cents = total_cents - (octave_idx * 1200.0)
            nearest_semitone = int(round(octave_cents / 100.0))
            cents_dev = octave_cents - (nearest_semitone * 100.0)
            cents_from_swara_center[i] = cents_dev

            pitch_class = nearest_semitone % 12
            swara_def = SWARA_DEFINITIONS[pitch_class]

            # Ambiguity check: if exactly at boundary with low confidence, classify as NONE
            if abs(cents_dev) > self.ambiguity_threshold_cents and confidences[i] < 0.60:
                raw_swaras.append("NONE")
                raw_symbols.append("NONE")
                raw_variants.append("NONE")
                raw_registers.append("NONE")
            else:
                raw_swaras.append(swara_def["name"])
                raw_symbols.append(swara_def["symbol"])
                raw_variants.append(swara_def["variant"])
                raw_registers.append(reg)

        # 5. Hysteresis Anti-Flicker Smoothing
        smoothed_symbols, smoothed_swaras, smoothed_variants, smoothed_registers = self._apply_hysteresis(
            raw_symbols, raw_swaras, raw_variants, raw_registers
        )

        # 6. Event-Level Segmentation & Transitions
        segments = self._extract_segments(
            timestamps, frequencies, smoothed_symbols, smoothed_swaras,
            smoothed_variants, smoothed_registers, cents_from_swara_center,
            confidences
        )

        # 7. Melodic Ornament Detection (Meend & Gamak/Andolan)
        ornaments = self._detect_ornaments(timestamps, frequencies, cents_from_tonic, smoothed_symbols, confidences)

        # 8. Pitch Class Distribution (PCD) & Dominant Swaras
        pcd, dominant_swaras = self._calculate_pcd(smoothed_symbols, confidences)

        # 9. Extract bigram transitions
        transitions = self._extract_transitions(segments)

        # 10. Summary metrics
        total_voiced = int(np.sum([1 for s in smoothed_symbols if s != "NONE"]))
        swara_coverage = float(total_voiced / num_frames * 100.0) if num_frames > 0 else 0.0
        unvoiced_pct = float(100.0 - swara_coverage)

        diagnostics = {
            "total_frames": num_frames,
            "total_voiced_swara_frames": total_voiced,
            "tonic_hz": tonic_hz,
            "tonic_confidence": tonic_confidence,
            "total_segments": len(segments),
            "total_ornament_phrases": len(ornaments),
        }

        return SwaraAnalysisResult(
            timestamps_seconds=timestamps,
            frequencies_hz=frequencies,
            swaras=smoothed_swaras,
            symbols=smoothed_symbols,
            variants=smoothed_variants,
            registers=smoothed_registers,
            cents_from_tonic=cents_from_tonic,
            cents_from_swara_center=cents_from_swara_center,
            confidence_values=confidences,
            segments=segments,
            pitch_class_distribution=pcd,
            dominant_swaras=dominant_swaras,
            transitions=transitions,
            ornaments=ornaments,
            swara_coverage_percentage=swara_coverage,
            unvoiced_percentage=unvoiced_pct,
            tonic_hz=tonic_hz,
            method="hysteresis_swara_pcd",
            diagnostics=diagnostics,
        )

    def _apply_hysteresis(
        self,
        symbols: List[str],
        swaras: List[str],
        variants: List[str],
        registers: List[str],
    ) -> Tuple[List[str], List[str], List[str], List[str]]:
        """
        Suppresses 1-to-2 frame transient switches (flicker) between adjacent swaras.
        """
        n = len(symbols)
        if n <= 2 or self.hysteresis_frames < 1:
            return symbols, swaras, variants, registers

        out_sym = list(symbols)
        out_swa = list(swaras)
        out_var = list(variants)
        out_reg = list(registers)

        for i in range(1, n - 1):
            # If frame i is an isolated 1-frame glitch between identical frames
            if out_sym[i] != "NONE" and out_sym[i - 1] != "NONE" and out_sym[i + 1] != "NONE":
                if out_sym[i - 1] == out_sym[i + 1] and out_sym[i] != out_sym[i - 1]:
                    out_sym[i] = out_sym[i - 1]
                    out_swa[i] = out_swa[i - 1]
                    out_var[i] = out_var[i - 1]
                    out_reg[i] = out_reg[i - 1]

        return out_sym, out_swa, out_var, out_reg

    def _extract_segments(
        self,
        timestamps: np.ndarray,
        frequencies: np.ndarray,
        symbols: List[str],
        swaras: List[str],
        variants: List[str],
        registers: List[str],
        cents_dev: np.ndarray,
        confidences: np.ndarray,
    ) -> List[SwaraSegment]:
        """
        Groups contiguous identical swaras into discrete SwaraSegments.
        """
        segments: List[SwaraSegment] = []
        n = len(symbols)
        if n == 0:
            return segments

        curr_sym = symbols[0]
        curr_start = 0

        for i in range(1, n + 1):
            if i == n or symbols[i] != curr_sym or registers[i] != registers[curr_start]:
                # Finalize current segment
                if curr_sym != "NONE":
                    seg_len = i - curr_start
                    if seg_len >= self.min_segment_frames:
                        t_start = float(timestamps[curr_start])
                        t_end = float(timestamps[i - 1])
                        dur = max(0.001, t_end - t_start)
                        f_mean = float(np.mean(frequencies[curr_start:i]))
                        dev_mean = float(np.mean(cents_dev[curr_start:i]))
                        c_mean = float(np.mean(confidences[curr_start:i]))

                        # Determine movement pattern
                        f_seg = frequencies[curr_start:i]
                        if len(f_seg) >= 5:
                            slope = (f_seg[-1] - f_seg[0]) / dur
                            if abs(slope) > 40.0:
                                move = "ascending" if slope > 0 else "descending"
                            else:
                                move = "steady"
                        else:
                            move = "steady"

                        segments.append(
                            SwaraSegment(
                                swara=swaras[curr_start],
                                symbol=curr_sym,
                                variant=variants[curr_start],
                                register=registers[curr_start],
                                start_time_seconds=round(t_start, 3),
                                end_time_seconds=round(t_end, 3),
                                duration_seconds=round(dur, 3),
                                mean_frequency_hz=round(f_mean, 2),
                                mean_cents_deviation=round(dev_mean, 1),
                                mean_confidence=round(c_mean, 3),
                                movement_type=move,
                            )
                        )

                if i < n:
                    curr_sym = symbols[i]
                    curr_start = i

        return segments

    def _detect_ornaments(
        self,
        timestamps: np.ndarray,
        frequencies: np.ndarray,
        cents_from_tonic: np.ndarray,
        symbols: List[str],
        confidences: np.ndarray,
    ) -> List[Dict[str, Any]]:
        """
        Detects prominent continuous musical ornaments:
        1. Meend (Glissando): Continuous monotonic pitch glides across >= 150 cents.
        2. Andolan / Gamak (Oscillation): Periodic vocal modulation around a note.
        """
        ornaments: List[Dict[str, Any]] = []
        n = len(timestamps)
        if n < 10:
            return ornaments

        # Find continuous voiced regions
        voiced_blocks: List[Tuple[int, int]] = []
        in_block = False
        start_idx = 0
        for i in range(n):
            if symbols[i] != "NONE" and confidences[i] >= 0.50:
                if not in_block:
                    in_block = True
                    start_idx = i
            else:
                if in_block:
                    in_block = False
                    if i - start_idx >= 8:
                        voiced_blocks.append((start_idx, i))
        if in_block and n - start_idx >= 8:
            voiced_blocks.append((start_idx, n))

        for b_start, b_end in voiced_blocks:
            cents_slice = cents_from_tonic[b_start:b_end]
            t_slice = timestamps[b_start:b_end]
            dur = float(t_slice[-1] - t_slice[0])
            total_interval = float(cents_slice[-1] - cents_slice[0])

            # 1. Meend Detection: smooth glide > 150 cents over at least 100 ms
            if abs(total_interval) >= 150.0 and dur >= 0.10:
                diffs = np.diff(cents_slice)
                consistent_dir = np.sum(diffs > 0) / len(diffs) if total_interval > 0 else np.sum(diffs < 0) / len(diffs)
                if consistent_dir >= 0.70:
                    ornaments.append({
                        "type": "meend",
                        "start_time_seconds": round(float(t_slice[0]), 3),
                        "end_time_seconds": round(float(t_slice[-1]), 3),
                        "duration_seconds": round(dur, 3),
                        "interval_cents": round(total_interval, 1),
                        "direction": "ascending" if total_interval > 0 else "descending",
                        "start_swara": symbols[b_start],
                        "end_swara": symbols[b_end - 1],
                    })

            # 2. Andolan / Gamak Detection: Oscillation around mean pitch with 2.5-8.5 Hz rate
            if dur >= 0.25:
                detrended = cents_slice - np.mean(cents_slice)
                p2p_amp = float(np.max(detrended) - np.min(detrended))
                zero_crossings = np.where(np.diff(np.sign(detrended)))[0]
                num_cycles = len(zero_crossings) / 2.0
                freq_hz = num_cycles / dur if dur > 0 else 0.0

                if 25.0 <= p2p_amp <= 200.0 and 2.5 <= freq_hz <= 8.5:
                    ornaments.append({
                        "type": "gamak_andolan",
                        "start_time_seconds": round(float(t_slice[0]), 3),
                        "end_time_seconds": round(float(t_slice[-1]), 3),
                        "duration_seconds": round(dur, 3),
                        "oscillation_rate_hz": round(freq_hz, 1),
                        "amplitude_cents": round(p2p_amp, 1),
                        "central_swara": symbols[(b_start + b_end) // 2],
                    })

        return ornaments

    def _calculate_pcd(
        self,
        symbols: List[str],
        confidences: np.ndarray,
    ) -> Tuple[Dict[str, float], List[Tuple[str, float]]]:
        """
        Calculates the 12-tone Pitch Class Distribution (PCD) weighted by confidence.
        """
        canonical_symbols = [s["symbol"] for s in SWARA_DEFINITIONS]
        pcd: Dict[str, float] = {sym: 0.0 for sym in canonical_symbols}

        total_weight = 0.0
        for i, sym in enumerate(symbols):
            if sym in pcd:
                w = float(confidences[i])
                pcd[sym] += w
                total_weight += w

        # Normalize PCD
        if total_weight > 0.0:
            for k in pcd:
                pcd[k] /= total_weight

        # Ranked dominant swaras
        sorted_swaras = sorted(pcd.items(), key=lambda item: item[1], reverse=True)
        dominant = [(sym, score) for sym, score in sorted_swaras if score > 0.01]

        return pcd, dominant

    def _extract_transitions(self, segments: List[SwaraSegment]) -> List[Tuple[str, str]]:
        """
        Extracts ordered pairs of swara transitions (bigrams) between consecutive voiced segments.
        """
        transitions: List[Tuple[str, str]] = []
        if len(segments) < 2:
            return transitions

        for i in range(len(segments) - 1):
            s1 = segments[i].symbol
            s2 = segments[i + 1].symbol
            if s1 != s2:
                transitions.append((s1, s2))

        return transitions

    def _empty_result(self, tonic_hz: float) -> SwaraAnalysisResult:
        """Returns empty SwaraAnalysisResult for 0-frame inputs."""
        empty_arr = np.array([], dtype=np.float32)
        return SwaraAnalysisResult(
            timestamps_seconds=empty_arr,
            frequencies_hz=empty_arr,
            swaras=[],
            symbols=[],
            variants=[],
            registers=[],
            cents_from_tonic=empty_arr,
            cents_from_swara_center=empty_arr,
            confidence_values=empty_arr,
            segments=[],
            pitch_class_distribution={s["symbol"]: 0.0 for s in SWARA_DEFINITIONS},
            dominant_swaras=[],
            transitions=[],
            ornaments=[],
            swara_coverage_percentage=0.0,
            unvoiced_percentage=100.0,
            tonic_hz=tonic_hz,
            method="hysteresis_swara_pcd",
            diagnostics={"status": "empty_input"},
        )

    def _fallback_unvoiced_result(
        self,
        timestamps: np.ndarray,
        frequencies: np.ndarray,
        tonic_hz: float,
    ) -> SwaraAnalysisResult:
        """Fallback result when tonic is missing or invalid."""
        num_frames = len(timestamps)
        zeros = np.zeros(num_frames, dtype=np.float32)
        none_list = ["NONE"] * num_frames
        return SwaraAnalysisResult(
            timestamps_seconds=timestamps,
            frequencies_hz=frequencies,
            swaras=none_list,
            symbols=none_list,
            variants=none_list,
            registers=none_list,
            cents_from_tonic=zeros,
            cents_from_swara_center=zeros,
            confidence_values=zeros,
            segments=[],
            pitch_class_distribution={s["symbol"]: 0.0 for s in SWARA_DEFINITIONS},
            dominant_swaras=[],
            transitions=[],
            ornaments=[],
            swara_coverage_percentage=0.0,
            unvoiced_percentage=100.0,
            tonic_hz=tonic_hz,
            method="hysteresis_swara_pcd",
            diagnostics={"status": "invalid_tonic_fallback"},
        )
