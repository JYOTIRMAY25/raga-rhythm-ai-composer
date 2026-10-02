"""
BeatTracker and Matra Alignment for RagaRhythm AI.

Converts low-level rhythmic features (onset novelty, timestamps, IOIs, and BPM)
from RhythmAnalyzer into a robust, continuous Hindustani rhythmic beat grid and
cyclic matra representation.

Key capabilities:
1. Dynamic programming beat tracking (Ellis-style) maintaining temporal continuity.
2. Explicit multi-hypothesis tempo evaluation (0.5x, 1.0x, 2.0x).
3. Robustness against missing beats, extra percussion strokes, and tempo drift.
4. Flexible Matra cycle alignment and Sam phase estimation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy import signal

from .rhythm_analyzer import RhythmFeatures

logger = logging.getLogger(__name__)


class BeatGrid(BaseModel):
    """
    Structured domain model representing a tracked beat grid and matra alignment.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    beat_times: np.ndarray = Field(..., description="1D float64 array of tracked beat timestamps in seconds")
    beat_frames: np.ndarray = Field(..., description="1D int64 array of novelty frame indices for each beat")
    beat_period: float = Field(default=0.0, description="Estimated average beat interval in seconds")
    bpm: Optional[float] = Field(default=None, description="Tempo in beats per minute derived from beat grid")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall beat tracking confidence [0.0, 1.0]")
    phase_offset_sec: float = Field(default=0.0, description="Time offset in seconds of the initial tracked beat")
    tempo_hypotheses: Dict[str, float] = Field(
        default_factory=dict,
        description="Relative alignment scores for candidate tempo multipliers (0.5x, 1.0x, 2.0x)"
    )
    selected_hypothesis: str = Field(default="1.0x", description="Selected tempo multiplier hypothesis")
    matra_indices: Optional[np.ndarray] = Field(
        default=None,
        description="1-indexed matra numbers (1..cycle_length) for each beat, or None if no cycle specified"
    )
    cycle_phases: Optional[np.ndarray] = Field(
        default=None,
        description="Normalized cycle phase in [0.0, 1.0) for each beat"
    )
    sam_timestamps: Optional[np.ndarray] = Field(
        default=None,
        description="Timestamps corresponding to Matra 1 (Sam / cycle start)"
    )
    cycle_length: Optional[int] = Field(
        default=None,
        description="Active rhythmic cycle length in matras (e.g. 16, 12, 10, 8, 7, 6)"
    )
    diagnostics: Dict[str, Any] = Field(default_factory=dict, description="Diagnostics and tracking metrics")

    @property
    def total_beats(self) -> int:
        """Total count of tracked beats."""
        return len(self.beat_times)

    def to_summary_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary summary."""
        return {
            "total_beats": self.total_beats,
            "beat_period": round(self.beat_period, 4),
            "bpm": round(self.bpm, 2) if self.bpm is not None else None,
            "confidence": round(self.confidence, 4),
            "phase_offset_sec": round(self.phase_offset_sec, 4),
            "selected_hypothesis": self.selected_hypothesis,
            "tempo_hypotheses": {k: round(v, 4) for k, v in self.tempo_hypotheses.items()},
            "cycle_length": self.cycle_length,
            "total_sam_cycles": len(self.sam_timestamps) if self.sam_timestamps is not None else 0,
            "diagnostics": self.diagnostics,
        }


class BeatTracker:
    """
    Hindustani rhythmic beat grid tracker and cyclic matra alignment engine.
    """

    def __init__(
        self,
        tightness: float = 100.0,
        min_bpm: float = 30.0,
        max_bpm: float = 360.0,
        hypotheses: Tuple[float, ...] = (0.5, 1.0, 2.0),
    ):
        """
        Initialize BeatTracker with configurable tracking parameters.

        Args:
            tightness: Penalty weight for deviations from the expected beat period in dynamic programming.
            min_bpm: Lower bound on valid tempo tracking.
            max_bpm: Upper bound on valid tempo tracking.
            hypotheses: Tempo candidate multipliers to evaluate (default: 0.5x, 1.0x, 2.0x).
        """
        self.tightness = float(tightness)
        self.min_bpm = float(min_bpm)
        self.max_bpm = float(max_bpm)
        self.hypotheses = hypotheses

    def _dp_track_beats_for_period(
        self,
        novelty: np.ndarray,
        period_frames: float,
        frame_rate: float,
    ) -> Tuple[np.ndarray, float]:
        """
        Execute dynamic programming beat tracking for a specific target period.

        Returns:
            Tuple of (beat_frames, average_objective_score).
        """
        N = len(novelty)
        if N < max(3, int(period_frames)):
            return np.zeros(0, dtype=np.int64), 0.0

        cumscore = np.copy(novelty)
        backlink = np.zeros(N, dtype=np.int64)

        min_delta = max(1, int(round(0.5 * period_frames)))
        max_delta = min(N - 1, int(round(2.0 * period_frames)))

        if min_delta >= max_delta:
            return np.zeros(0, dtype=np.int64), 0.0

        deltas = np.arange(min_delta, max_delta + 1)
        trans_costs = - self.tightness * (np.log(deltas / float(period_frames))) ** 2

        for t in range(min_delta, N):
            valid_len = min(len(deltas), t)
            if valid_len <= 0:
                continue
            
            prev_scores = cumscore[t - deltas[:valid_len]] + trans_costs[:valid_len]
            best_idx = int(np.argmax(prev_scores))
            cumscore[t] = novelty[t] + prev_scores[best_idx]
            backlink[t] = t - deltas[best_idx]

        # Backtrack from optimal terminal beat in the final period window
        end_window = max(1, min(N, int(round(period_frames * 1.5))))
        best_end = N - end_window + int(np.argmax(cumscore[N - end_window:]))

        beat_list = [best_end]
        curr = best_end
        while curr > min_delta and backlink[curr] > 0:
            curr = int(backlink[curr])
            beat_list.append(curr)

        beat_list.reverse()
        beats = np.array(beat_list, dtype=np.int64)

        if len(beats) < 2:
            return beats, 0.0

        # Calculate average alignment score
        avg_score = float(np.mean(novelty[beats]))

        return beats, avg_score

    def evaluate_tempo_hypotheses(
        self,
        novelty: np.ndarray,
        base_bpm: float,
        frame_rate: float,
    ) -> Tuple[str, Dict[str, float], float, np.ndarray]:
        """
        Explicitly evaluate 0.5x, 1.0x, and 2.0x tempo hypotheses.

        Returns:
            Tuple of (selected_hypothesis_name, hypothesis_scores_dict, selected_bpm, best_beat_frames).
        """
        hyp_scores: Dict[str, float] = {}
        hyp_beats: Dict[str, np.ndarray] = {}
        hyp_bpms: Dict[str, float] = {}

        total_energy = float(np.sum(novelty))

        for mult in self.hypotheses:
            cand_bpm = base_bpm * mult
            if cand_bpm < self.min_bpm or cand_bpm > self.max_bpm:
                continue

            name = f"{mult:.1f}x"
            period_frames = (60.0 * frame_rate) / cand_bpm
            beats, score = self._dp_track_beats_for_period(novelty, period_frames, frame_rate)

            if len(beats) >= 2 and total_energy > 1e-6:
                # 1. Onset energy coverage: proportion of total novelty energy explained by the beat grid
                covered_energy = float(np.sum(novelty[beats]))
                coverage = min(1.0, covered_energy / total_energy)

                # 2. Regularity bonus: penalize variance in inter-beat intervals
                diffs = np.diff(beats)
                cv = float(np.std(diffs) / (np.mean(diffs) + 1e-6))
                regularity = max(0.0, 1.0 - min(1.0, cv))

                # 3. Average peak score
                peak_accuracy = score

                # Combined hypothesis score with base tempo prior weight (1.0x slight prior)
                prior_bonus = 1.05 if mult == 1.0 else 1.0
                total_score = (0.5 * coverage + 0.3 * regularity + 0.2 * peak_accuracy) * prior_bonus
            else:
                total_score = 0.0

            hyp_scores[name] = float(total_score)
            hyp_beats[name] = beats
            hyp_bpms[name] = cand_bpm

        if not hyp_scores:
            return "1.0x", {"1.0x": 0.0}, base_bpm, np.zeros(0, dtype=np.int64)

        # Normalize hypothesis scores to relative proportions
        max_s = max(hyp_scores.values())
        if max_s > 1e-6:
            norm_scores = {k: v / max_s for k, v in hyp_scores.items()}
        else:
            norm_scores = {k: 0.0 for k in hyp_scores}

        # Select hypothesis with highest score (defaulting to 1.0x on near-ties)
        best_name = "1.0x" if "1.0x" in norm_scores and norm_scores["1.0x"] >= 0.95 else max(norm_scores, key=lambda k: norm_scores[k])
        best_bpm = hyp_bpms.get(best_name, base_bpm)
        best_beats = hyp_beats.get(best_name, np.zeros(0, dtype=np.int64))

        return best_name, norm_scores, best_bpm, best_beats


    def align_matras(
        self,
        beat_times: np.ndarray,
        novelty_envelope: np.ndarray,
        frame_rate: float,
        cycle_length: int,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        """
        Map tracked beats onto integer matra indices (1..cycle_length) and estimate Sam phase.

        Args:
            beat_times: 1D array of beat timestamps in seconds.
            novelty_envelope: 1D onset novelty curve.
            frame_rate: Analysis frame rate in Hz.
            cycle_length: Total beats per rhythmic cycle (e.g., 16, 12, 10, 8, 7, 6).

        Returns:
            Tuple of (matra_indices, cycle_phases, sam_timestamps, sam_phase_offset_sec):
                - matra_indices: 1D array of 1-indexed integers in [1, cycle_length].
                - cycle_phases: 1D array of floats in [0.0, 1.0).
                - sam_timestamps: 1D array of timestamps where matra == 1 (Sam).
                - sam_phase_offset_sec: timestamp of the first detected Sam beat.
        """
        M = int(cycle_length)
        N = len(beat_times)
        if M <= 0 or N == 0:
            return (
                np.zeros(0, dtype=np.int64),
                np.zeros(0, dtype=np.float64),
                np.zeros(0, dtype=np.float64),
                0.0,
            )

        # Convert beat times to frame indices
        beat_frames = np.clip(
            np.round(beat_times * frame_rate).astype(np.int64),
            0,
            len(novelty_envelope) - 1,
        )

        # Evaluate all candidate cycle phase offsets k in 0..M-1
        # Objective: find offset k where cycle boundaries (beat index % M == k) have maximum onset accent
        phase_scores = np.zeros(M, dtype=np.float64)
        for k in range(M):
            cycle_boundary_indices = np.arange(k, N, M)
            if len(cycle_boundary_indices) > 0:
                boundary_frames = beat_frames[cycle_boundary_indices]
                # Mean novelty energy at candidate Sam beats
                phase_scores[k] = float(np.mean(novelty_envelope[boundary_frames]))

        best_k = int(np.argmax(phase_scores))

        # Assign 1-indexed matra numbers: matra = (i - best_k) % M + 1
        beat_indices = np.arange(N)
        matra_indices = ((beat_indices - best_k) % M + 1).astype(np.int64)

        # Cycle phase in [0.0, 1.0)
        cycle_phases = ((beat_indices - best_k) % M).astype(np.float64) / float(M)

        # Sam timestamps (where matra == 1)
        sam_mask = matra_indices == 1
        sam_timestamps = beat_times[sam_mask]
        sam_phase_offset = float(sam_timestamps[0]) if len(sam_timestamps) > 0 else float(beat_times[0])

        return matra_indices, cycle_phases, sam_timestamps, sam_phase_offset

    def track(
        self,
        rhythm_features: RhythmFeatures,
        cycle_length: Optional[int] = None,
    ) -> BeatGrid:
        """
        Track rhythmic beat grid and optional matra alignment from RhythmFeatures.

        Args:
            rhythm_features: Output from RhythmAnalyzer.analyze().
            cycle_length: Optional rhythmic cycle length in beats (e.g. 16, 12, 10, 8, 7, 6).

        Returns:
            BeatGrid object containing beat times, periods, BPM, and matra alignment.
        """
        novelty = rhythm_features.novelty_envelope
        frame_rate = rhythm_features.frame_rate
        base_bpm = rhythm_features.estimated_bpm

        # Guard: silence, empty novelty, or no estimated BPM
        if (
            novelty is None
            or len(novelty) == 0
            or base_bpm is None
            or base_bpm <= 0.0
            or rhythm_features.total_onsets < 2
            or float(np.max(novelty)) < 1e-4
        ):
            return BeatGrid(
                beat_times=np.zeros(0, dtype=np.float64),
                beat_frames=np.zeros(0, dtype=np.int64),
                beat_period=0.0,
                bpm=None,
                confidence=0.0,
                phase_offset_sec=0.0,
                tempo_hypotheses={},
                selected_hypothesis="none",
                cycle_length=cycle_length,
                diagnostics={"reason": "insufficient_rhythmic_energy_or_silence"},
            )

        # 1. Evaluate tempo hypotheses (0.5x, 1.0x, 2.0x) and get initial beat frames
        hyp_name, hyp_scores, tracking_bpm, beat_frames = self.evaluate_tempo_hypotheses(
            novelty, base_bpm, frame_rate
        )

        if len(beat_frames) < 2:
            return BeatGrid(
                beat_times=np.zeros(0, dtype=np.float64),
                beat_frames=np.zeros(0, dtype=np.int64),
                beat_period=0.0,
                bpm=None,
                confidence=0.0,
                phase_offset_sec=0.0,
                tempo_hypotheses=hyp_scores,
                selected_hypothesis=hyp_name,
                cycle_length=cycle_length,
                diagnostics={"reason": "insufficient_tracked_beats"},
            )

        # Convert frames to timestamps in seconds
        beat_times = beat_frames.astype(np.float64) / float(frame_rate)

        # Calculate robust beat interval statistics
        diffs = np.diff(beat_times)
        valid_diffs = diffs[diffs > 0]
        beat_period = float(np.median(valid_diffs)) if len(valid_diffs) > 0 else (60.0 / tracking_bpm)
        grid_bpm = float(60.0 / beat_period) if beat_period > 0 else tracking_bpm

        phase_offset = float(beat_times[0])

        # Confidence Estimation
        # Alignment with novelty envelope peaks
        mean_peak_novelty = float(np.mean(novelty[beat_frames]))
        # Period regularity
        period_std = float(np.std(valid_diffs)) if len(valid_diffs) > 0 else 0.0
        regularity = max(0.0, 1.0 - min(1.0, period_std / (beat_period + 1e-6)))
        grid_confidence = float(np.clip(0.5 * mean_peak_novelty + 0.5 * regularity, 0.0, 1.0))

        # 2. Matra Alignment (if cycle_length provided)
        matra_indices = None
        cycle_phases = None
        sam_timestamps = None
        if cycle_length is not None and cycle_length > 0:
            matra_indices, cycle_phases, sam_timestamps, _ = self.align_matras(
                beat_times, novelty, frame_rate, cycle_length
            )

        diagnostics = {
            "mean_peak_novelty": round(mean_peak_novelty, 4),
            "period_regularity": round(regularity, 4),
            "tracking_bpm": round(tracking_bpm, 2),
            "raw_beat_count": len(beat_times),
        }

        return BeatGrid(
            beat_times=beat_times,
            beat_frames=beat_frames,
            beat_period=round(beat_period, 5),
            bpm=round(grid_bpm, 2),
            confidence=round(grid_confidence, 4),
            phase_offset_sec=round(phase_offset, 5),
            tempo_hypotheses=hyp_scores,
            selected_hypothesis=hyp_name,
            matra_indices=matra_indices,
            cycle_phases=cycle_phases,
            sam_timestamps=sam_timestamps,
            cycle_length=cycle_length,
            diagnostics=diagnostics,
        )
