"""
TonicResolver for RagaRhythm AI.

Resolves the true fundamental tonic (Sa) frequency of an Indian classical music
recording by generating multiple plausible candidates (including octave equivalents,
Pa/Ma transpositions, and contour peaks) and evaluating them against independent
acoustic and melodic evidence.

Prevents cascading errors caused by tonic estimator fifth (Pa) or fourth (Ma) locking.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy import signal

from backend.app.analysis.pitch_extractor import PitchExtractionResult
from backend.app.analysis.tonic_estimator import (
    TonicEstimationResult,
    TonicEstimator,
    hz_to_note_info,
)

logger = logging.getLogger(__name__)


class TonicCandidate(BaseModel):
    """Detailed candidate tonic evaluation."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    frequency_hz: float = Field(..., description="Candidate tonic fundamental frequency in Hz")
    note_name: str = Field(..., description="Nearest 12-TET note name (e.g. 'D3', 'C#3')")
    octave: int = Field(default=3, description="Estimated MIDI octave")
    cents_deviation: float = Field(default=0.0, description="Deviation in cents from equal temperament")
    candidate_type: str = Field(default="estimator_base", description="Origin: estimator_base, octave_lower, octave_upper, pa_transposition, ma_transposition, contour_peak")
    harmonic_score: float = Field(default=0.0, ge=0.0, le=1.0)
    drone_score: float = Field(default=0.0, ge=0.0, le=1.0)
    pitch_stability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    swara_coherence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    feature_scores: Dict[str, float] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frequency_hz": round(self.frequency_hz, 2),
            "note_name": self.note_name,
            "octave": self.octave,
            "cents_deviation": round(self.cents_deviation, 1),
            "candidate_type": self.candidate_type,
            "harmonic_score": round(self.harmonic_score, 3),
            "drone_score": round(self.drone_score, 3),
            "pitch_stability_score": round(self.pitch_stability_score, 3),
            "swara_coherence_score": round(self.swara_coherence_score, 3),
            "overall_score": round(self.overall_score, 3),
            "confidence": round(self.confidence, 3),
            "feature_scores": self.feature_scores,
        }


class TonicResolutionResult(BaseModel):
    """Structured output payload for resolved tonic."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    selected_tonic: TonicCandidate = Field(..., description="Top ranked resolved tonic candidate")
    candidates: List[TonicCandidate] = Field(..., description="All evaluated candidates sorted descending by overall score")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Calibrated confidence in tonic resolution")
    ambiguity_flag: bool = Field(default=False, description="True if top candidate is closely contested by runner up")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Supporting acoustic and melodic metrics")
    rejected_candidates: List[TonicCandidate] = Field(default_factory=list, description="Candidates eliminated due to low coherence")
    method: str = Field(default="multi_feature_tonic_resolver", description="Resolution algorithm identifier")
    diagnostics: Dict[str, Any] = Field(default_factory=dict)

    @property
    def tonic_hz(self) -> float:
        return self.selected_tonic.frequency_hz

    @property
    def note_name(self) -> str:
        return self.selected_tonic.note_name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_tonic": self.selected_tonic.to_dict(),
            "candidates": [c.to_dict() for c in self.candidates],
            "confidence": round(self.confidence, 3),
            "ambiguity_flag": self.ambiguity_flag,
            "evidence": self.evidence,
            "rejected_candidates": [c.to_dict() for c in self.rejected_candidates],
            "method": self.method,
            "diagnostics": self.diagnostics,
        }


class TonicResolver:
    """
    Multi-Candidate Tonic Resolver for Hindustani Classical Music.

    Resolves the Sa fundamental by arbitrating among candidate frequencies generated from:
    1. Upstream TonicEstimator baseline.
    2. Octave multiplications/divisions.
    3. Fifth (Pa) / Fourth (Ma) harmonic transposition hypotheses.
    4. Continuous pitch contour F0 peak clustering.

    Evaluates candidates across four independent dimensions:
    - Harmonic Spectral Support
    - Tanpura Drone Resonance
    - Melodic Pitch Stability (Nyasa frame concentration)
    - Swara Coherence (alignment with 12-TET/shruti semitone grid)
    """

    MIN_TONIC_HZ = 100.0
    MAX_TONIC_HZ = 350.0
    AMBIGUITY_THRESHOLD = 0.045

    def __init__(
        self,
        weight_harmonic: float = 0.25,
        weight_drone: float = 0.25,
        weight_pitch_stability: float = 0.25,
        weight_swara_coherence: float = 0.25,
    ) -> None:
        total_w = weight_harmonic + weight_drone + weight_pitch_stability + weight_swara_coherence
        if total_w <= 0.0:
            total_w = 1.0
        self.w_harmonic = weight_harmonic / total_w
        self.w_drone = weight_drone / total_w
        self.w_pitch_stability = weight_pitch_stability / total_w
        self.w_swara_coherence = weight_swara_coherence / total_w
        self.tonic_estimator = TonicEstimator()

    def resolve(
        self,
        waveform: np.ndarray,
        sample_rate: int = 22050,
        pitch_result: Optional[Union[PitchExtractionResult, Dict[str, Any]]] = None,
        tonic_estimate: Optional[Union[TonicEstimationResult, Dict[str, Any], float]] = None,
    ) -> TonicResolutionResult:
        """
        Resolves the true Sa tonic from audio and pitch evidence.
        """
        # 1. Sanitize waveform
        if waveform is None or len(waveform) == 0:
            return self._insufficient_evidence_result("Empty or null waveform provided.")

        waveform = np.asarray(waveform, dtype=np.float32)
        if waveform.ndim > 1:
            waveform = waveform.flatten()

        waveform = np.nan_to_num(waveform, nan=0.0, posinf=0.0, neginf=0.0)
        rms = float(np.sqrt(np.mean(waveform ** 2)))
        if rms < 1e-5:
            return self._insufficient_evidence_result("Silent waveform (RMS < 1e-5).")

        # 2. Extract baseline tonic estimate if not supplied
        base_hz = 0.0
        base_conf = 0.0
        if tonic_estimate is not None:
            if isinstance(tonic_estimate, TonicEstimationResult):
                base_hz = float(tonic_estimate.tonic_hz)
                base_conf = float(tonic_estimate.confidence)
            elif isinstance(tonic_estimate, dict):
                base_hz = float(tonic_estimate.get("tonic_hz", 0.0))
                base_conf = float(tonic_estimate.get("confidence", 0.5))
            elif isinstance(tonic_estimate, (int, float)):
                base_hz = float(tonic_estimate)
                base_conf = 0.5
        
        if base_hz <= 0.0 or not np.isfinite(base_hz):
            try:
                est_res = self.tonic_estimator.estimate(waveform, sample_rate)
                base_hz = float(est_res.tonic_hz)
                base_conf = float(est_res.confidence)
            except Exception as e:
                logger.warning(f"TonicEstimator fallback failed: {e}")
                base_hz = 140.0
                base_conf = 0.2

        # 3. Extract pitch contour frequencies
        pitch_freqs = np.array([], dtype=np.float64)
        pitch_confs = np.array([], dtype=np.float64)
        if pitch_result is not None:
            if isinstance(pitch_result, PitchExtractionResult):
                vmask = pitch_result.voiced_mask
                pitch_freqs = pitch_result.frequencies_hz[vmask]
                pitch_confs = pitch_result.confidence_values[vmask]
            elif isinstance(pitch_result, dict):
                freqs = np.asarray(pitch_result.get("frequencies_hz", []), dtype=np.float64)
                vmask = np.asarray(pitch_result.get("voiced_mask", []), dtype=bool)
                if len(freqs) > 0 and len(vmask) == len(freqs):
                    pitch_freqs = freqs[vmask]
                else:
                    pitch_freqs = freqs[freqs > 0.0]

        # 4. Generate candidate pool
        raw_candidates = self._generate_candidates(base_hz, pitch_freqs)

        # 5. Compute FFT spectrum once for all candidates
        fft_freqs, fft_mag = self._compute_spectrum(waveform, sample_rate)

        # 6. Score each candidate
        evaluated_candidates: List[TonicCandidate] = []
        for cand_hz, c_type in raw_candidates:
            cand = self._score_candidate(
                cand_hz=cand_hz,
                cand_type=c_type,
                fft_freqs=fft_freqs,
                fft_mag=fft_mag,
                pitch_freqs=pitch_freqs,
                pitch_confs=pitch_confs,
                base_hz=base_hz,
                base_conf=base_conf,
            )
            evaluated_candidates.append(cand)

        # Sort candidates descending by overall score
        evaluated_candidates.sort(key=lambda c: c.overall_score, reverse=True)

        if not evaluated_candidates:
            return self._insufficient_evidence_result("No valid tonic candidates generated.")

        top_cand = evaluated_candidates[0]
        runner_up = evaluated_candidates[1] if len(evaluated_candidates) > 1 else None

        # Determine ambiguity flag and final confidence
        ambiguity_flag = False
        if runner_up and (top_cand.overall_score - runner_up.overall_score) < self.AMBIGUITY_THRESHOLD:
            ambiguity_flag = True
            confidence = round(float(top_cand.overall_score * 0.88), 3)
        else:
            confidence = round(float(top_cand.overall_score), 3)

        rejected = [c for c in evaluated_candidates[1:] if c.overall_score < 0.25]
        valid_candidates = [c for c in evaluated_candidates if c.overall_score >= 0.25] or [top_cand]

        evidence = {
            "total_candidates_evaluated": len(evaluated_candidates),
            "original_estimator_hz": round(base_hz, 2),
            "original_estimator_confidence": round(base_conf, 3),
            "selected_hz": round(top_cand.frequency_hz, 2),
            "selected_type": top_cand.candidate_type,
            "top_score": round(top_cand.overall_score, 4),
            "runner_up_score": round(runner_up.overall_score, 4) if runner_up else 0.0,
            "score_margin": round((top_cand.overall_score - runner_up.overall_score), 4) if runner_up else 1.0,
            "ambiguity": ambiguity_flag,
        }

        return TonicResolutionResult(
            selected_tonic=top_cand,
            candidates=valid_candidates,
            confidence=confidence,
            ambiguity_flag=ambiguity_flag,
            evidence=evidence,
            rejected_candidates=rejected,
            method="multi_feature_tonic_resolver",
            diagnostics={
                "w_harmonic": self.w_harmonic,
                "w_drone": self.w_drone,
                "w_pitch_stability": self.w_pitch_stability,
                "w_swara_coherence": self.w_swara_coherence,
            },
        )

    def _generate_candidates(
        self,
        base_hz: float,
        pitch_freqs: np.ndarray,
    ) -> List[Tuple[float, str]]:
        """
        Generates mathematically and musically plausible Sa tonic candidates.
        """
        candidates: List[Tuple[float, str]] = []

        if base_hz > 0.0 and np.isfinite(base_hz):
            # 1. Base estimator candidate
            if self.MIN_TONIC_HZ <= base_hz <= self.MAX_TONIC_HZ:
                candidates.append((base_hz, "estimator_base"))

            # 2. Octave equivalents
            if self.MIN_TONIC_HZ <= (base_hz / 2.0) <= self.MAX_TONIC_HZ:
                candidates.append((base_hz / 2.0, "octave_lower"))
            if self.MIN_TONIC_HZ <= (base_hz * 2.0) <= self.MAX_TONIC_HZ:
                candidates.append((base_hz * 2.0, "octave_upper"))

            # 3. Fifth (Pa) Transposition Hypotheses:
            # If estimator picked Pa (ratio 3/2 = 1.5), then Sa is base_hz / 1.5 = base_hz * 2/3
            # Or if base_hz was lower octave Pa, Sa is base_hz * 4/3
            pa_sa_lower = base_hz * (2.0 / 3.0)
            if self.MIN_TONIC_HZ <= pa_sa_lower <= self.MAX_TONIC_HZ:
                candidates.append((pa_sa_lower, "pa_transposition"))

            pa_sa_upper = base_hz * (4.0 / 3.0)
            if self.MIN_TONIC_HZ <= pa_sa_upper <= self.MAX_TONIC_HZ:
                candidates.append((pa_sa_upper, "pa_transposition"))

            # 4. Fourth (Shuddha Ma) Transposition Hypotheses:
            # If estimator picked Ma (ratio 4/3), then Sa is base_hz / (4/3) = base_hz * 3/4
            # Or base_hz * 3/2
            ma_sa_lower = base_hz * (3.0 / 4.0)
            if self.MIN_TONIC_HZ <= ma_sa_lower <= self.MAX_TONIC_HZ:
                candidates.append((ma_sa_lower, "ma_transposition"))

            ma_sa_upper = base_hz * (3.0 / 2.0)
            if self.MIN_TONIC_HZ <= ma_sa_upper <= self.MAX_TONIC_HZ:
                candidates.append((ma_sa_upper, "ma_transposition"))

        # 5. Extract persistent voiced pitch peaks from F0 contour
        if len(pitch_freqs) >= 20:
            valid_p = pitch_freqs[(pitch_freqs >= self.MIN_TONIC_HZ) & (pitch_freqs <= self.MAX_TONIC_HZ)]
            if len(valid_p) >= 10:
                hist, bin_edges = np.histogram(valid_p, bins=60)
                peak_indices = signal.find_peaks(hist, height=max(3, int(len(valid_p) * 0.05)), distance=4)[0]
                for p_idx in peak_indices:
                    center_hz = float(0.5 * (bin_edges[p_idx] + bin_edges[p_idx + 1]))
                    candidates.append((center_hz, "contour_peak"))

        # Deduplicate candidates within 30 cents
        deduped: List[Tuple[float, str]] = []
        for hz, c_type in candidates:
            if not np.isfinite(hz) or hz <= 0.0:
                continue
            is_dup = False
            for existing_hz, _ in deduped:
                cents_diff = abs(1200.0 * np.log2(hz / existing_hz))
                if cents_diff < 30.0:
                    is_dup = True
                    break
            if not is_dup:
                deduped.append((hz, c_type))

        return deduped

    def _compute_spectrum(self, waveform: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, np.ndarray]:
        """Computes average magnitude spectrum using Hann-windowed Welch FFT."""
        n_fft = 4096
        hop = 1024
        window = np.hanning(n_fft)
        
        num_frames = max(1, (len(waveform) - n_fft) // hop + 1)
        mag_accum = np.zeros(n_fft // 2 + 1, dtype=np.float64)

        for i in range(min(num_frames, 60)):
            start = i * hop
            segment = waveform[start:start + n_fft]
            if len(segment) < n_fft:
                segment = np.pad(segment, (0, n_fft - len(segment)))
            windowed = segment * window
            spec = np.abs(np.fft.rfft(windowed))
            mag_accum += spec

        mag_accum /= max(1, min(num_frames, 60))
        freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
        return freqs, mag_accum

    def _score_candidate(
        self,
        cand_hz: float,
        cand_type: str,
        fft_freqs: np.ndarray,
        fft_mag: np.ndarray,
        pitch_freqs: np.ndarray,
        pitch_confs: np.ndarray,
        base_hz: float,
        base_conf: float,
    ) -> TonicCandidate:
        """
        Scores an individual tonic candidate across the four independent dimensions.
        """
        note_name, cents_dev = hz_to_note_info(cand_hz)
        midi_val = int(round(69.0 + 12.0 * np.log2(cand_hz / 440.0)))
        octave = (midi_val // 12) - 1

        # 1. Harmonic Score (Fundamental + Harmonics 1f, 2f, 3f, 4f, 5f)
        score_harmonic = self._calc_harmonic_score(cand_hz, fft_freqs, fft_mag)

        # 2. Drone Score (Tanpura resonance at 1.0f Sa, 1.5f Pa, 2.0f Sa')
        score_drone = self._calc_drone_score(cand_hz, fft_freqs, fft_mag)

        # 3. Pitch Stability Score (Voiced contour frame density near Sa and Pa)
        score_pitch_stability = self._calc_pitch_stability_score(cand_hz, pitch_freqs, pitch_confs)

        # 4. Swara Coherence Score (Alignment of voiced frames with 12-TET/shruti grid relative to cand_hz)
        score_swara_coherence = self._calc_swara_coherence_score(cand_hz, pitch_freqs)

        # Register alignment relative to median vocal pitch
        register_penalty = 0.0
        if len(pitch_freqs) >= 15:
            med_f0 = float(np.median(pitch_freqs))
            if med_f0 > 0:
                cents_above_med = 1200.0 * np.log2(cand_hz / med_f0)
                if cents_above_med > 700.0:
                    # Candidate is an octave above the singer's melodic center
                    register_penalty = 0.22

        type_bonus = 0.0
        if cand_type == "estimator_base":
            type_bonus += 0.02 * base_conf
        elif "pa_transposition" in cand_type:
            type_bonus += 0.02

        raw_score = (
            self.w_harmonic * score_harmonic +
            self.w_drone * score_drone +
            self.w_pitch_stability * score_pitch_stability +
            self.w_swara_coherence * score_swara_coherence +
            type_bonus -
            register_penalty
        )
        overall_score = float(np.clip(raw_score, 0.0, 1.0))
        if not np.isfinite(overall_score):
            overall_score = 0.0

        feature_scores = {
            "harmonic": round(score_harmonic, 3),
            "drone": round(score_drone, 3),
            "pitch_stability": round(score_pitch_stability, 3),
            "swara_coherence": round(score_swara_coherence, 3),
        }

        return TonicCandidate(
            frequency_hz=round(cand_hz, 2),
            note_name=note_name,
            octave=octave,
            cents_deviation=round(cents_dev, 1),
            candidate_type=cand_type,
            harmonic_score=round(score_harmonic, 3),
            drone_score=round(score_drone, 3),
            pitch_stability_score=round(score_pitch_stability, 3),
            swara_coherence_score=round(score_swara_coherence, 3),
            overall_score=round(overall_score, 3),
            confidence=round(overall_score, 3),
            feature_scores=feature_scores,
        )

    def _calc_harmonic_score(self, f0: float, freqs: np.ndarray, mag: np.ndarray) -> float:
        """Evaluates harmonic comb energy at 1f, 2f, 3f, 4f, 5f."""
        if f0 <= 0.0 or len(freqs) == 0:
            return 0.0

        harmonic_weights = [1.0, 0.8, 0.6, 0.4, 0.3]
        total_energy = 0.0
        max_possible = 0.0

        for h_idx, w in enumerate(harmonic_weights, 1):
            h_freq = f0 * h_idx
            if h_freq >= freqs[-1]:
                break
            # Find peak in +/- 3% tolerance window
            low_f = h_freq * 0.97
            high_f = h_freq * 1.03
            mask = (freqs >= low_f) & (freqs <= high_f)
            if np.any(mask):
                h_mag = float(np.max(mag[mask]))
                total_energy += w * h_mag
            max_possible += w

        peak_mag = float(np.max(mag)) if len(mag) > 0 and np.max(mag) > 0 else 1.0
        normalized = total_energy / (max_possible * peak_mag)
        return float(np.clip(normalized * 1.8, 0.0, 1.0))

    def _calc_drone_score(self, f0: float, freqs: np.ndarray, mag: np.ndarray) -> float:
        """Evaluates Tanpura drone intervals: Sa (1.0f), Pa (1.5f), Sa' (2.0f)."""
        if f0 <= 0.0 or len(freqs) == 0:
            return 0.0

        drone_intervals = [(1.0, 0.5), (1.5, 0.3), (2.0, 0.2)]
        drone_energy = 0.0

        for ratio, w in drone_intervals:
            target_f = f0 * ratio
            if target_f >= freqs[-1]:
                break
            mask = (freqs >= target_f * 0.98) & (freqs <= target_f * 1.02)
            if np.any(mask):
                drone_energy += w * float(np.max(mag[mask]))

        peak_mag = float(np.max(mag)) if len(mag) > 0 and np.max(mag) > 0 else 1.0
        score = drone_energy / peak_mag
        return float(np.clip(score * 1.6, 0.0, 1.0))

    def _calc_pitch_stability_score(
        self,
        cand_hz: float,
        pitch_freqs: np.ndarray,
        pitch_confs: np.ndarray,
    ) -> float:
        """Measures voiced pitch dwell time on candidate unison Sa, octave Sa, and Pa."""
        if len(pitch_freqs) < 10 or cand_hz <= 0.0:
            return 0.5  # Neutral default when contour is unavailable

        # Calculate cents difference from candidate Sa: F_0 / cand_hz
        cents_from_sa = 1200.0 * np.log2(pitch_freqs / cand_hz)

        # 1. Unison Sa (within +/- 35 cents of 0 cents)
        unison_sa = np.abs(cents_from_sa) < 35.0
        # 2. Octave Sa (within +/- 35 cents of +1200 or -1200 cents)
        octave_sa = (np.abs(cents_from_sa - 1200.0) < 35.0) | (np.abs(cents_from_sa + 1200.0) < 35.0)
        # 3. Pa (within +/- 35 cents of +700 cents or -500 cents)
        near_pa = (np.abs(cents_from_sa - 700.0) < 35.0) | (np.abs(cents_from_sa + 500.0) < 35.0)

        unison_ratio = float(np.sum(unison_sa) / len(pitch_freqs))
        octave_ratio = float(np.sum(octave_sa) / len(pitch_freqs))
        pa_ratio = float(np.sum(near_pa) / len(pitch_freqs))

        # Direct unison Sa is the strongest melodic evidence (1.0), octave Sa is secondary (0.55)
        # Penalty if candidate has near-zero unison Sa but high Pa (candidate is actually Pa)
        pa_penalty = 0.40 if (unison_ratio < 0.04 and pa_ratio > 0.20) else 0.0

        raw_stability = (unison_ratio * 1.0) + (octave_ratio * 0.55) + (pa_ratio * 0.35) - pa_penalty
        return float(np.clip(raw_stability, 0.0, 1.0))

    def _calc_swara_coherence_score(self, cand_hz: float, pitch_freqs: np.ndarray) -> float:
        """
        Evaluates swara grid alignment:
        Calculates how tightly voiced frames cluster around the 12 canonical semitones
        (0, 100, 200... cents) vs inter-semitone quarter-tone dissonance (50, 150... cents).
        """
        if len(pitch_freqs) < 15 or cand_hz <= 0.0:
            return 0.5

        # Cents mod 100 distance from nearest semitone
        cents_rel = 1200.0 * np.log2(pitch_freqs / cand_hz)
        cents_mod_100 = np.mod(cents_rel, 100.0)
        # Distance to nearest semitone center [0, 50]
        dist_to_semitone = np.minimum(cents_mod_100, 100.0 - cents_mod_100)

        # On-grid frames: within 22 cents of semitone center
        on_grid_ratio = float(np.sum(dist_to_semitone <= 22.0) / len(dist_to_semitone))
        # Off-grid dissonant frames: in [35, 50] cents
        off_grid_ratio = float(np.sum(dist_to_semitone >= 35.0) / len(dist_to_semitone))

        coherence = on_grid_ratio - (off_grid_ratio * 0.75)
        return float(np.clip(coherence, 0.0, 1.0))

    def _insufficient_evidence_result(self, reason: str) -> TonicResolutionResult:
        """Constructs a safe zero-confidence fallback for silence or invalid input."""
        fallback_cand = TonicCandidate(
            frequency_hz=0.0,
            note_name="N/A",
            octave=0,
            cents_deviation=0.0,
            candidate_type="insufficient_evidence",
            harmonic_score=0.0,
            drone_score=0.0,
            pitch_stability_score=0.0,
            swara_coherence_score=0.0,
            overall_score=0.0,
            confidence=0.0,
            feature_scores={},
        )
        return TonicResolutionResult(
            selected_tonic=fallback_cand,
            candidates=[fallback_cand],
            confidence=0.0,
            ambiguity_flag=True,
            evidence={"reason": reason},
            rejected_candidates=[],
            method="insufficient_evidence",
            diagnostics={},
        )
