"""
Rhythm grid generator mapping melodic events into metric Tala cycles.
"""

from __future__ import annotations

from typing import Any, Dict, List
from backend.app.composition.composition_models import CompositionCycle, SwaraEvent
from backend.app.composition.tala_constraints import TalaConstraints


class RhythmGenerator:
    """Organizes raw swara event dicts into typed CompositionCycle and SwaraEvent models."""

    def __init__(self, tala_constraints: TalaConstraints):
        self.tala = tala_constraints

    def structure_cycles(self, raw_cycles_events: List[List[Dict[str, Any]]]) -> List[CompositionCycle]:
        """Converts raw event lists into validated CompositionCycle structures."""
        structured_cycles: List[CompositionCycle] = []

        for cycle_idx, raw_events in enumerate(raw_cycles_events, start=1):
            typed_events: List[SwaraEvent] = []
            for ev in raw_events:
                # Validate cycle and matra integrity
                typed_event = SwaraEvent(
                    cycle=ev.get("cycle", cycle_idx),
                    vibhag=ev.get("vibhag", 1),
                    matra=ev.get("matra", 1),
                    subdivision=ev.get("subdivision", 0),
                    swara=ev["swara"],
                    octave=ev.get("octave", 0),
                    pitch_hz=ev["pitch_hz"],
                    duration_matras=ev.get("duration_matras", 1.0),
                    theka_bol=ev.get("theka_bol"),
                    ornament=ev.get("ornament", "straight"),
                    is_vadi=ev.get("is_vadi", False),
                    is_samvadi=ev.get("is_samvadi", False),
                    is_sam_landing=ev.get("is_sam_landing", False),
                )
                typed_events.append(typed_event)

            structured_cycles.append(
                CompositionCycle(cycle_number=cycle_idx, events=typed_events)
            )

        return structured_cycles
