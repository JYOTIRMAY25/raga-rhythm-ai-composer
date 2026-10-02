"""
Main Algorithmic Composition Orchestrator.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from backend.app.composition.composition_models import (
    CompositionRequest,
    SymbolicComposition,
)
from backend.app.composition.composition_validator import CompositionValidator
from backend.app.composition.melody_generator import MelodyGenerator
from backend.app.composition.raga_constraints import (
    STANDARD_TONIC_FREQUENCIES,
    RagaConstraints,
)
from backend.app.composition.rhythm_generator import RhythmGenerator
from backend.app.composition.tala_constraints import TalaConstraints

logger = logging.getLogger(__name__)


class CompositionEngine:
    """Core algorithmic engine generating deterministic, validated Indian classical compositions."""

    def compose(self, request: CompositionRequest) -> SymbolicComposition:
        """
        Orchestrates deterministic composition generation adhering strictly
        to the chosen Raga, Tala, tempo, and duration.
        """
        # 1. Resolve Tonic
        tonic_name = (request.tonic or "C#").strip().upper()
        tonic_hz = (
            request.tonic_hz
            if request.tonic_hz and request.tonic_hz > 0
            else STANDARD_TONIC_FREQUENCIES.get(tonic_name, 138.59)
        )

        # 2. Build Constraints
        raga_const = RagaConstraints(
            raga_id=request.raga_id, tonic_hz=tonic_hz, tonic_name=tonic_name
        )
        tala_const = TalaConstraints(
            tala_id=request.tala_id, bpm=request.tempo_bpm
        )

        # 3. Calculate Cycles
        total_cycles = tala_const.calculate_cycle_count(request.duration_seconds)
        total_matras = total_cycles * tala_const.matras
        actual_duration = total_cycles * tala_const.seconds_per_cycle

        # 4. Generate Melody
        seed_value = request.seed if request.seed is not None else 42
        melody_gen = MelodyGenerator(
            raga_constraints=raga_const,
            tala_constraints=tala_const,
            creativity_score=request.creativity_score,
            seed=seed_value,
        )
        raw_cycle_events = melody_gen.generate_composition_melody(
            total_cycles=total_cycles, style=request.style_id
        )

        # 5. Structure into Metric Cycles
        rhythm_gen = RhythmGenerator(tala_constraints=tala_const)
        structured_cycles = rhythm_gen.structure_cycles(raw_cycle_events)

        # Flatten linear events list
        all_events = [ev for cycle in structured_cycles for ev in cycle.events]

        # 6. Validate Composition
        validator = CompositionValidator(
            raga_constraints=raga_const, tala_constraints=tala_const
        )
        validation_result = validator.validate(structured_cycles)

        comp_id = f"comp_{uuid.uuid4().hex[:12]}"
        title = f"Bandish in Raga {raga_const.name} ({tala_const.name}, {request.tempo_bpm} BPM)"

        return SymbolicComposition(
            composition_id=comp_id,
            title=title,
            raga_id=raga_const.raga_id,
            raga_name=raga_const.name,
            thaat=raga_const.thaat,
            tala_id=tala_const.tala_id,
            tala_name=tala_const.name,
            matras=tala_const.matras,
            vibhag_structure=tala_const.vibhag_str,
            tempo_bpm=request.tempo_bpm,
            laya=tala_const.laya_category,
            tonic_note=tonic_name,
            tonic_hz=tonic_hz,
            style=request.style_id,
            total_cycles=total_cycles,
            total_matras=total_matras,
            duration_seconds=round(actual_duration, 2),
            events=all_events,
            cycles=structured_cycles,
            seed=seed_value,
            validation=validation_result,
        )


# Singleton composition engine instance
composition_engine = CompositionEngine()
