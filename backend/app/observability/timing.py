"""
High-resolution monotonic stage duration measurement for RagaRhythm AI.
Uses time.perf_counter() to ensure non-decreasing monotonic measurements,
resilient against wall-clock synchronization jumps.
"""

from __future__ import annotations

import time
from typing import Dict, Optional


class StageTimer:
    """
    Lightweight, exception-resilient timer for measuring durations of pipeline stages.
    Guarantees monotonic elapsed time calculations with defensive error handling.
    """

    def __init__(self) -> None:
        self._timings: Dict[str, float] = {}
        self._active_stages: Dict[str, float] = {}

    def start_stage(self, stage_name: str) -> None:
        """Starts timing a named stage using the monotonic perf_counter clock."""
        try:
            self._active_stages[stage_name] = time.perf_counter()
        except Exception:
            pass

    def stop_stage(self, stage_name: str) -> float:
        """
        Stops timing a named stage, computes elapsed duration in milliseconds,
        records it, and returns the duration. Returns 0.0 on error or missing stage.
        """
        try:
            start_time = self._active_stages.pop(stage_name, None)
            if start_time is None:
                return self._timings.get(stage_name, 0.0)

            duration_ms = max(0.0, (time.perf_counter() - start_time) * 1000.0)
            rounded_ms = round(duration_ms, 2)
            self._timings[stage_name] = rounded_ms
            return rounded_ms
        except Exception:
            return 0.0

    def record_duration(self, stage_name: str, duration_ms: float) -> None:
        """Manually records an already computed stage duration in milliseconds."""
        try:
            self._timings[stage_name] = round(max(0.0, float(duration_ms)), 2)
        except Exception:
            pass

    def get_duration(self, stage_name: str) -> Optional[float]:
        """Retrieves recorded duration for a stage, or None if not recorded."""
        return self._timings.get(stage_name)

    def to_dict(self) -> Dict[str, float]:
        """Returns a copy of all recorded stage timings in milliseconds."""
        return dict(self._timings)


class StageTimerScope:
    """
    Context manager scope for timing an individual stage block.
    """

    def __init__(self, timer: StageTimer, stage_name: str) -> None:
        self._timer = timer
        self._stage_name = stage_name

    def __enter__(self) -> StageTimerScope:
        self._timer.start_stage(self._stage_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._timer.stop_stage(self._stage_name)
