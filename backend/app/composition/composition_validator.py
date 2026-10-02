"""
Composition Validator evaluating musicological invariants and metric consistency.
"""

from __future__ import annotations

from typing import List
from backend.app.composition.composition_models import (
    CompositionCycle,
    SwaraEvent,
    ValidationDiagnostic,
    ValidationResult,
)
from backend.app.composition.raga_constraints import RagaConstraints, normalize_swara_symbol
from backend.app.composition.tala_constraints import TalaConstraints


class CompositionValidator:
    """Evaluates generated classical compositions against strict raga, tala, and acoustic rules."""

    def __init__(self, raga_constraints: RagaConstraints, tala_constraints: TalaConstraints):
        self.raga = raga_constraints
        self.tala = tala_constraints

    def validate(self, cycles: List[CompositionCycle]) -> ValidationResult:
        """Runs comprehensive validation across all cycles and events in the composition."""
        diagnostics: List[ValidationDiagnostic] = []
        total_swara_events = 0
        compliant_swara_events = 0
        total_cycle_beats = 0
        expected_cycle_beats = 0
        sam_resolution_passed = True

        if not cycles:
            diagnostics.append(
                ValidationDiagnostic(
                    severity="error",
                    rule="non_empty_composition",
                    message="Composition contains no cycles or events.",
                    location="root",
                )
            )
            return ValidationResult(
                valid=False,
                swara_compliance_score=0.0,
                tala_alignment_score=0.0,
                sam_resolution_passed=False,
                diagnostics=diagnostics,
            )

        for cycle in cycles:
            cycle_matra_sum = 0.0
            expected_cycle_beats += self.tala.matras

            for ev in cycle.events:
                total_swara_events += 1
                base_swara, oct_offset = normalize_swara_symbol(ev.swara)

                # 1. Check Varjit (forbidden) swaras
                if base_swara in self.raga.forbidden_swaras:
                    diagnostics.append(
                        ValidationDiagnostic(
                            severity="error",
                            rule="varjit_swara_violation",
                            message=f"Forbidden swara '{base_swara}' in Raga {self.raga.name} detected.",
                            location=f"Cycle {ev.cycle}, Matra {ev.matra}",
                        )
                    )
                else:
                    compliant_swara_events += 1

                # 2. Check register bounds (-1: Mandra, 0: Madhya, +1: Tara)
                if ev.octave < -1 or ev.octave > 1:
                    diagnostics.append(
                        ValidationDiagnostic(
                            severity="warning",
                            rule="octave_range_exceeded",
                            message=f"Swara '{ev.swara}' octave {ev.octave} outside canonical 3-saptak range.",
                            location=f"Cycle {ev.cycle}, Matra {ev.matra}",
                        )
                    )

                # 3. Check temporal position bounds
                if ev.matra < 1 or ev.matra > self.tala.matras:
                    diagnostics.append(
                        ValidationDiagnostic(
                            severity="error",
                            rule="matra_index_out_of_bounds",
                            message=f"Matra index {ev.matra} exceeds Tala cycle bounds [1, {self.tala.matras}].",
                            location=f"Cycle {ev.cycle}, Matra {ev.matra}",
                        )
                    )

                # 4. Check pitch sanity
                if ev.pitch_hz <= 20.0 or ev.pitch_hz >= 2000.0:
                    diagnostics.append(
                        ValidationDiagnostic(
                            severity="error",
                            rule="acoustic_pitch_bounds",
                            message=f"Pitch frequency {ev.pitch_hz:.1f} Hz outside acoustic vocal range.",
                            location=f"Cycle {ev.cycle}, Matra {ev.matra}",
                        )
                    )

                cycle_matra_sum += ev.duration_matras

            total_cycle_beats += cycle_matra_sum

            # Check cycle duration matches Tala matra count
            if abs(cycle_matra_sum - self.tala.matras) > 0.01:
                diagnostics.append(
                    ValidationDiagnostic(
                        severity="error",
                        rule="cycle_matra_duration_mismatch",
                        message=f"Cycle {cycle.cycle_number} duration ({cycle_matra_sum:.1f} matras) != {self.tala.matras}.",
                        location=f"Cycle {cycle.cycle_number}",
                    )
                )

        # 5. Check Sam landing on final cycle
        last_cycle = cycles[-1]
        first_event_of_last = last_cycle.events[0] if last_cycle.events else None
        if first_event_of_last:
            base_first, _ = normalize_swara_symbol(first_event_of_last.swara)
            # Sam resolution should land on Sa, Pa, or Vadi
            valid_sam_notes = {"S", "P", self.raga.vadi}
            if base_first not in valid_sam_notes:
                sam_resolution_passed = False
                diagnostics.append(
                    ValidationDiagnostic(
                        severity="warning",
                        rule="sam_resolution_swara",
                        message=f"Final Sam landed on '{base_first}', traditional cadence resolves to Sa or Vadi.",
                        location=f"Cycle {last_cycle.cycle_number}, Matra 1",
                    )
                )

        swara_compliance = (
            compliant_swara_events / total_swara_events if total_swara_events > 0 else 1.0
        )
        tala_alignment = (
            1.0 if abs(total_cycle_beats - expected_cycle_beats) < 0.01 else 0.8
        )

        has_errors = any(d.severity == "error" for d in diagnostics)
        is_valid = not has_errors and swara_compliance >= 0.95

        return ValidationResult(
            valid=is_valid,
            swara_compliance_score=round(swara_compliance, 3),
            tala_alignment_score=round(tala_alignment, 3),
            sam_resolution_passed=sam_resolution_passed,
            diagnostics=diagnostics,
        )
