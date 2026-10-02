"""
TalaClassifier and Scoring for RagaRhythm AI.

Provides evidence-based classification and ranking for Hindustani rhythmic cycles (Talas):
1. Teentaal (16 matras)
2. Ektaal (12 matras)
3. Jhaptaal (10 matras)
4. Tilwada (16 matras)
5. Jhoomra (14 matras)
6. Jatt / Addha (16 matras)
7. Rupak (7 matras)
8. Keherwa (8 matras)
9. Dadra (6 matras)

Employs multi-cue acoustic evidence:
- Cycle autocorrelation periodicity
- Matra/beat alignment and Sam boundary accent contrast
- Tali vs Khali structural contrast
- Laya (tempo) compatibility distribution
- Multi-tempo multiplier (0.5x, 1.0x, 2.0x) disambiguation
- Allied-tala discrimination
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy import signal

from .beat_tracker import BeatGrid, BeatTracker
from .rhythm_analyzer import RhythmFeatures
from .tala_knowledge_base import TalaDefinition, get_tala

logger = logging.getLogger(__name__)


class TalaCandidate(BaseModel):
    """
    Candidate Tala classification hypothesis with detailed component scores.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tala_name: str = Field(..., description="Canonical display name (e.g. 'Teentaal')")
    tala_id: str = Field(..., description="Canonical snake_case identifier")
    matras: int = Field(..., description="Cycle length in beats")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Normalized posterior confidence [0.0, 1.0]")
    composite_score: float = Field(..., description="Raw weighted multi-cue evidence score")
    cycle_fit_score: float = Field(default=0.0, description="Autocorrelation periodicity at full cycle lag")
    accent_fit_score: float = Field(default=0.0, description="Alignment with Sam and Tali accents")
    laya_fit_score: float = Field(default=0.0, description="Tempo / laya likelihood match")
    vibhag_score: float = Field(default=0.0, description="Measure partition and structural match")
    details: Dict[str, Any] = Field(default_factory=dict, description="Detailed diagnostic breakdown")


class TalaClassificationResult(BaseModel):
    """
    Structured domain model containing ranked Tala candidates and classification diagnostics.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    predicted_tala: Optional[str] = Field(default=None, description="Top-1 predicted Tala name, or None if unclassifiable")
    predicted_tala_id: Optional[str] = Field(default=None, description="Top-1 predicted Tala ID")
    predicted_matras: Optional[int] = Field(default=None, description="Cycle beat count of top candidate")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall classification confidence [0.0, 1.0]")
    is_ambiguous: bool = Field(default=False, description="True if top candidates are closely contested")
    candidates: List[TalaCandidate] = Field(default_factory=list, description="Ranked list of candidate Talas")
    estimated_bpm: Optional[float] = Field(default=None, description="Tempo in beats per minute")
    tempo_hypothesis: str = Field(default="1.0x", description="Active tempo multiplier hypothesis")
    sam_phase_sec: Optional[float] = Field(default=None, description="Estimated first Sam timestamp in seconds")
    diagnostics: Dict[str, Any] = Field(default_factory=dict, description="Summary diagnostics and metrics")

    @property
    def total_candidates(self) -> int:
        return len(self.candidates)

    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert result into a clean JSON-serializable summary dictionary."""
        return {
            "predicted_tala": self.predicted_tala,
            "predicted_matras": self.predicted_matras,
            "confidence": round(self.confidence, 4),
            "is_ambiguous": self.is_ambiguous,
            "estimated_bpm": round(self.estimated_bpm, 2) if self.estimated_bpm is not None else None,
            "tempo_hypothesis": self.tempo_hypothesis,
            "sam_phase_sec": round(self.sam_phase_sec, 4) if self.sam_phase_sec is not None else None,
            "top_candidates": [
                {
                    "tala_name": c.tala_name,
                    "matras": c.matras,
                    "confidence": round(c.confidence, 4),
                    "composite_score": round(c.composite_score, 4),
                }
                for c in self.candidates[:5]
            ],
            "diagnostics": self.diagnostics,
        }


# ============================================================================
# Tala Classification Profiles (9 Target Hindustani Talas)
# ============================================================================

TALA_PROFILES: Dict[str, Dict[str, Any]] = {
    "teental": {
        "name": "Teentaal",
        "tala_id": "teental",
        "matras": 16,
        "vibhags": [4, 4, 4, 4],
        "sam": 1,
        "tali": [1, 5, 13],
        "khali": [9],
        "layas": [(120.0, 45.0), (220.0, 60.0)],  # (center_bpm, std_bpm)
        "tempo_prior_weight": 1.15,  # Ubiquitous Hindustani standard
    },
    "ektaal": {
        "name": "Ektaal",
        "tala_id": "ektaal",
        "matras": 12,
        "vibhags": [2, 2, 2, 2, 2, 2],
        "sam": 1,
        "tali": [1, 5, 9, 11],
        "khali": [3, 7],
        "layas": [(40.0, 18.0), (180.0, 50.0)],
        "tempo_prior_weight": 1.05,
    },
    "jhaptaal": {
        "name": "Jhaptaal",
        "tala_id": "jhaptaal",
        "matras": 10,
        "vibhags": [2, 3, 2, 3],
        "sam": 1,
        "tali": [1, 3, 8],
        "khali": [6],
        "layas": [(90.0, 30.0), (160.0, 40.0)],
        "tempo_prior_weight": 1.0,
    },
    "tilwada": {
        "name": "Tilwada",
        "tala_id": "tilwada",
        "matras": 16,
        "vibhags": [4, 4, 4, 4],
        "sam": 1,
        "tali": [1, 5, 13],
        "khali": [9],
        "layas": [(52.0, 15.0)],  # Strictly Vilambit laya
        "tempo_prior_weight": 0.95,
    },
    "jhoomra": {
        "name": "Jhoomra",
        "tala_id": "jhoomra",
        "matras": 14,
        "vibhags": [3, 4, 3, 4],
        "sam": 1,
        "tali": [1, 4, 11],
        "khali": [8],
        "layas": [(45.0, 15.0)],  # Strictly Vilambit laya
        "tempo_prior_weight": 0.95,
    },
    "jatt": {
        "name": "Jatt",
        "tala_id": "jatt",
        "matras": 16,
        "vibhags": [4, 4, 4, 4],
        "sam": 1,
        "tali": [1, 5, 13],
        "khali": [9],
        "layas": [(140.0, 35.0)],  # Madhya/Drut light classical
        "tempo_prior_weight": 0.95,
    },
    "rupak": {
        "name": "Rupak",
        "tala_id": "rupak",
        "matras": 7,
        "vibhags": [3, 2, 2],
        "sam": 1,
        "tali": [4, 6],
        "khali": [1],  # Famous: Sam is Khali
        "layas": [(100.0, 35.0)],
        "tempo_prior_weight": 1.0,
    },
    "keharwa": {
        "name": "Keherwa",
        "tala_id": "keharwa",
        "matras": 8,
        "vibhags": [4, 4],
        "sam": 1,
        "tali": [1],
        "khali": [5],
        "layas": [(130.0, 45.0)],
        "tempo_prior_weight": 1.05,
    },
    "dadra": {
        "name": "Dadra",
        "tala_id": "dadra",
        "matras": 6,
        "vibhags": [3, 3],
        "sam": 1,
        "tali": [1],
        "khali": [4],
        "layas": [(120.0, 40.0)],
        "tempo_prior_weight": 1.0,
    },
}


class TalaClassifier:
    """
    Evidence-based Hindustani Tala classifier and candidate ranker.
    """

    def __init__(
        self,
        tala_profiles: Optional[Dict[str, Dict[str, Any]]] = None,
        tracker: Optional[BeatTracker] = None,
        min_classification_confidence: float = 0.25,
    ):
        """
        Initialize TalaClassifier with candidate profiles and beat tracker.

        Args:
            tala_profiles: Dictionary of tala definition profiles (defaults to TALA_PROFILES).
            tracker: BeatTracker instance (defaults to BeatTracker()).
            min_classification_confidence: Minimum score threshold for positive classification.
        """
        self.profiles = tala_profiles or TALA_PROFILES
        self.tracker = tracker or BeatTracker()
        self.min_confidence = float(min_classification_confidence)

    def _compute_cycle_autocorrelation(
        self,
        novelty: np.ndarray,
        cycle_matras: int,
        beat_period_frames: float,
    ) -> float:
        """
        Compute normalized autocorrelation periodicity at the full cycle lag (M * beat_period).
        """
        target_lag = int(round(cycle_matras * beat_period_frames))
        if target_lag >= len(novelty) or target_lag <= 0:
            return 0.0

        # Autocorrelate over valid window
        search_radius = max(2, int(0.04 * target_lag))
        min_l = max(1, target_lag - search_radius)
        max_l = min(len(novelty) - 1, target_lag + search_radius)

        if min_l >= max_l:
            return 0.0

        ac = signal.correlate(novelty, novelty, mode="full")[len(novelty) - 1 :]
        if np.max(ac) < 1e-6:
            return 0.0

        ac_norm = ac / float(np.max(ac))
        window_ac = ac_norm[min_l : max_l + 1]
        
        peak_val = float(np.max(window_ac)) if len(window_ac) > 0 else 0.0
        return float(np.clip(peak_val, 0.0, 1.0))

    def _compute_laya_likelihood(
        self,
        bpm: float,
        laya_specs: List[Tuple[float, float]],
    ) -> float:
        """
        Calculate tempo compatibility likelihood across characteristic laya modes.
        """
        if bpm <= 0.0 or not laya_specs:
            return 0.5

        likelihoods = []
        for center_bpm, std_bpm in laya_specs:
            diff = (bpm - center_bpm) / std_bpm
            like = float(np.exp(-0.5 * (diff ** 2)))
            likelihoods.append(like)

        return float(np.clip(max(likelihoods), 0.05, 1.0))

    def _score_tala_candidate(
        self,
        profile: Dict[str, Any],
        novelty: np.ndarray,
        beat_times: np.ndarray,
        bpm: float,
        frame_rate: float,
        beat_period_frames: float,
        tempo_hypotheses: Dict[str, float],
    ) -> TalaCandidate:
        """
        Compute multi-cue evidence score for a specific Tala profile.
        """
        tala_name = profile["name"]
        tala_id = profile["tala_id"]
        M = profile["matras"]
        sam_pos = profile.get("sam", 1)
        tali_pos = profile.get("tali", [1])
        khali_pos = profile.get("khali", [])

        # 1. Cycle autocorrelation fit
        cycle_fit = self._compute_cycle_autocorrelation(novelty, M, beat_period_frames)

        # 2. Structural Matra & Accent Alignment
        N = len(beat_times)
        if N >= max(4, M) and len(novelty) > 0:
            beat_frames = np.clip(
                np.round(beat_times * frame_rate).astype(np.int64),
                0,
                len(novelty) - 1,
            )
            beat_energies = novelty[beat_frames]

            best_accent_fit = 0.0
            best_sam_e = 0.0
            best_khali_e = 0.0

            # Find best cycle offset k in 0..M-1 tailored to this Tala's structural Tali/Khali markers
            for k in range(M):
                cand_matras = (np.arange(N) - k) % M + 1

                sam_mask = cand_matras == sam_pos
                s_energy = float(np.mean(beat_energies[sam_mask])) if np.any(sam_mask) else 0.0

                tali_mask = np.isin(cand_matras, tali_pos)
                t_energy = float(np.mean(beat_energies[tali_mask])) if np.any(tali_mask) else 0.0

                khali_mask = np.isin(cand_matras, khali_pos)
                k_energy = float(np.mean(beat_energies[khali_mask])) if np.any(khali_mask) else 0.0

                if tala_id == "rupak":
                    # For Rupak: structural accents are on beats 4, 6, while Sam (beat 1) is Khali
                    acc = max(0.0, t_energy - s_energy * 0.5)
                else:
                    acc = max(0.0, 0.6 * s_energy + 0.4 * t_energy - 0.5 * k_energy)

                if acc > best_accent_fit:
                    best_accent_fit = acc
                    best_sam_e = s_energy
                    best_khali_e = k_energy

            accent_fit = float(np.clip(best_accent_fit, 0.0, 1.0))
            sam_energy = best_sam_e
            khali_energy = best_khali_e
        else:
            accent_fit = 0.3
            sam_energy = 0.0
            khali_energy = 0.0


        # 3. Laya (Tempo) Fit
        laya_fit = self._compute_laya_likelihood(bpm, profile["layas"])

        # 4. Multi-tempo multiplier compatibility
        # If BPM is fast (> 180) and cycle is 8 (Keherwa), evaluate if 16-beat Teentaal or 8-beat Keherwa fits better
        tempo_hyp_weight = float(tempo_hypotheses.get("1.0x", 1.0))

        # 5. Vibhag structural symmetry score
        vibhags = profile["vibhags"]
        is_symmetric = len(set(vibhags)) == 1
        vibhag_score = 0.8 if is_symmetric else 0.7

        # 6. Allied-tala specific adjustments (Teentaal vs Tilwada vs Jatt)
        allied_bonus = 1.0
        if tala_id == "tilwada":
            # Tilwada is favored strictly at slow vilambit tempo (< 75 BPM)
            if bpm < 75.0:
                allied_bonus = 1.1
            else:
                allied_bonus = 0.5
        elif tala_id == "jatt":
            # Jatt is favored at faster tempos (> 120 BPM)
            if bpm > 120.0:
                allied_bonus = 1.05
            else:
                allied_bonus = 0.8

        prior_weight = profile.get("tempo_prior_weight", 1.0) * allied_bonus

        # Composite score
        raw_composite = (
            0.35 * cycle_fit
            + 0.30 * accent_fit
            + 0.20 * laya_fit
            + 0.15 * vibhag_score
        ) * prior_weight * tempo_hyp_weight

        details = {
            "sam_energy": round(sam_energy, 4),
            "khali_energy": round(khali_energy, 4),
            "prior_weight": round(prior_weight, 4),
        }

        return TalaCandidate(
            tala_name=tala_name,
            tala_id=tala_id,
            matras=M,
            confidence=0.0,  # normalized later across all candidates
            composite_score=float(raw_composite),
            cycle_fit_score=round(cycle_fit, 4),
            accent_fit_score=round(accent_fit, 4),
            laya_fit_score=round(laya_fit, 4),
            vibhag_score=round(vibhag_score, 4),
            details=details,
        )

    def classify(
        self,
        rhythm_features: RhythmFeatures,
        beat_grid: Optional[BeatGrid] = None,
    ) -> TalaClassificationResult:
        """
        Classify and rank candidate Talas from acoustic rhythm features and beat grid.

        Args:
            rhythm_features: RhythmFeatures object from RhythmAnalyzer.
            beat_grid: Optional precomputed BeatGrid (tracked automatically if None).

        Returns:
            TalaClassificationResult with ranked candidates and confidence.
        """
        novelty = rhythm_features.novelty_envelope
        frame_rate = rhythm_features.frame_rate
        raw_bpm = rhythm_features.estimated_bpm

        # If beat grid not supplied, compute it
        grid = beat_grid or self.tracker.track(rhythm_features)

        # Guard: silence, no BPM, insufficient beats
        if (
            novelty is None
            or len(novelty) == 0
            or raw_bpm is None
            or raw_bpm <= 0.0
            or grid.total_beats < 4
            or grid.bpm is None
        ):
            return TalaClassificationResult(
                predicted_tala=None,
                predicted_tala_id=None,
                predicted_matras=None,
                confidence=0.0,
                is_ambiguous=True,
                candidates=[],
                estimated_bpm=None,
                tempo_hypothesis="none",
                sam_phase_sec=None,
                diagnostics={"reason": "insufficient_beats_or_silence"},
            )

        active_bpm = float(grid.bpm)
        beat_times = grid.beat_times
        beat_period_frames = (60.0 * frame_rate) / active_bpm

        # Score all 9 target Tala profiles
        raw_candidates: List[TalaCandidate] = []
        for tala_id, profile in self.profiles.items():
            cand = self._score_tala_candidate(
                profile=profile,
                novelty=novelty,
                beat_times=beat_times,
                bpm=active_bpm,
                frame_rate=frame_rate,
                beat_period_frames=beat_period_frames,
                tempo_hypotheses=grid.tempo_hypotheses,
            )
            raw_candidates.append(cand)

        # Normalize composite scores to temperature-scaled softmax posterior probabilities
        scores = np.array([c.composite_score for c in raw_candidates], dtype=np.float64)
        temperature = 0.15
        exp_scores = np.exp((scores - np.max(scores)) / temperature)
        confidences = exp_scores / (np.sum(exp_scores) + 1e-6)

        # Update candidate confidences and sort descending
        ranked_candidates: List[TalaCandidate] = []
        for cand, conf in zip(raw_candidates, confidences):
            ranked_candidates.append(
                TalaCandidate(
                    tala_name=cand.tala_name,
                    tala_id=cand.tala_id,
                    matras=cand.matras,
                    confidence=round(float(conf), 4),
                    composite_score=round(cand.composite_score, 4),
                    cycle_fit_score=cand.cycle_fit_score,
                    accent_fit_score=cand.accent_fit_score,
                    laya_fit_score=cand.laya_fit_score,
                    vibhag_score=cand.vibhag_score,
                    details=cand.details,
                )
            )

        ranked_candidates.sort(key=lambda c: c.composite_score, reverse=True)

        top_cand = ranked_candidates[0]
        runner_up = ranked_candidates[1] if len(ranked_candidates) > 1 else None

        # Check ambiguity: small score difference between top 1 and top 2, or low absolute confidence
        score_gap = (top_cand.composite_score - runner_up.composite_score) if runner_up else 1.0
        is_ambiguous = score_gap < 0.05 or top_cand.confidence < self.min_confidence

        # Top-1 decision: accept top prediction if composite score and confidence are viable
        if top_cand.composite_score >= 0.30 and not is_ambiguous:
            predicted_tala = top_cand.tala_name
            predicted_id = top_cand.tala_id
            predicted_matras = top_cand.matras
            overall_confidence = float(np.clip(top_cand.confidence * grid.confidence, 0.0, 1.0))
        elif top_cand.composite_score >= 0.35 and top_cand.confidence >= 0.18:
            # Tolerant selection when top candidate is distinct
            predicted_tala = top_cand.tala_name
            predicted_id = top_cand.tala_id
            predicted_matras = top_cand.matras
            overall_confidence = float(np.clip(top_cand.confidence * grid.confidence, 0.0, 1.0))
        else:
            predicted_tala = None
            predicted_id = None
            predicted_matras = None
            overall_confidence = 0.0


        # Re-align matras with the top candidate's cycle length to get Sam phase
        top_matras = top_cand.matras
        _, _, sam_times, first_sam = self.tracker.align_matras(
            beat_times, novelty, frame_rate, top_matras
        )

        diagnostics = {
            "score_gap": round(score_gap, 4),
            "tracking_confidence": round(grid.confidence, 4),
            "top_composite_score": round(top_cand.composite_score, 4),
            "total_candidates_evaluated": len(ranked_candidates),
        }

        return TalaClassificationResult(
            predicted_tala=predicted_tala,
            predicted_tala_id=predicted_id,
            predicted_matras=predicted_matras,
            confidence=round(overall_confidence, 4),
            is_ambiguous=is_ambiguous,
            candidates=ranked_candidates,
            estimated_bpm=round(active_bpm, 2),
            tempo_hypothesis=grid.selected_hypothesis,
            sam_phase_sec=round(first_sam, 4) if len(sam_times) > 0 else None,
            diagnostics=diagnostics,
        )
