"""
Lightweight in-process metrics registry for RagaRhythm AI.
Tracks request and job counters, stage duration aggregates, and system gauges.
Thread-safe, bounded, low-overhead, and free from high-cardinality dimensions.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional


class LatencyTracker:
    """
    Bounded, thread-safe statistical accumulator for durations in milliseconds.
    Avoids storing raw samples to keep memory strictly bounded O(1).
    """

    def __init__(self) -> None:
        self.count: int = 0
        self.total_ms: float = 0.0
        self.min_ms: Optional[float] = None
        self.max_ms: Optional[float] = None

    def record(self, duration_ms: float) -> None:
        val = max(0.0, float(duration_ms))
        self.count += 1
        self.total_ms += val
        if self.min_ms is None or val < self.min_ms:
            self.min_ms = round(val, 2)
        if self.max_ms is None or val > self.max_ms:
            self.max_ms = round(val, 2)

    def to_dict(self) -> Dict[str, Any]:
        avg_ms = round(self.total_ms / self.count, 2) if self.count > 0 else 0.0
        return {
            "count": self.count,
            "total_ms": round(self.total_ms, 2),
            "avg_ms": avg_ms,
            "min_ms": self.min_ms or 0.0,
            "max_ms": self.max_ms or 0.0,
        }

    def reset(self) -> None:
        self.count = 0
        self.total_ms = 0.0
        self.min_ms = None
        self.max_ms = None


class MetricsRegistry:
    """
    Central thread-safe in-process metrics container.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()

        # Request counters & latency
        self._requests_total: int = 0
        self._requests_failed: int = 0
        self._request_latency = LatencyTracker()

        # Job counters & latency
        self._jobs_created: int = 0
        self._jobs_completed: int = 0
        self._jobs_failed: int = 0
        self._jobs_cancelled: int = 0
        self._job_analysis_duration = LatencyTracker()

        # Stage durations: bounded dictionary of known DSP stages
        self._stage_latencies: Dict[str, LatencyTracker] = {}

        # Error counts: bounded dictionary of safe error codes
        self._failure_counts_by_code: Dict[str, int] = {}

        # Optional gauge providers
        self._gauge_provider: Optional[Callable[[], Dict[str, Any]]] = None

    def set_gauge_provider(self, provider: Callable[[], Dict[str, Any]]) -> None:
        """Registers a callback providing real-time worker and queue gauges."""
        with self._lock:
            self._gauge_provider = provider

    def record_request(self, duration_ms: float, is_error: bool = False) -> None:
        """Records an HTTP request completion and its latency."""
        try:
            with self._lock:
                self._requests_total += 1
                if is_error:
                    self._requests_failed += 1
                self._request_latency.record(duration_ms)
        except Exception:
            pass

    def record_job_created(self) -> None:
        """Increments job creation counter."""
        try:
            with self._lock:
                self._jobs_created += 1
        except Exception:
            pass

    def record_job_completed(self, duration_ms: float) -> None:
        """Increments completed jobs counter and updates analysis duration stats."""
        try:
            with self._lock:
                self._jobs_completed += 1
                self._job_analysis_duration.record(duration_ms)
        except Exception:
            pass

    def record_job_failed(self, error_code: str = "INTERNAL_ERROR") -> None:
        """Increments failed jobs counter and updates failure code taxonomy counts."""
        try:
            with self._lock:
                self._jobs_failed += 1
                # Sanitize error code key to ensure bounded cardinality
                safe_code = str(error_code)[:32].upper()
                self._failure_counts_by_code[safe_code] = (
                    self._failure_counts_by_code.get(safe_code, 0) + 1
                )
        except Exception:
            pass

    def record_job_cancelled(self) -> None:
        """Increments cancelled jobs counter."""
        try:
            with self._lock:
                self._jobs_cancelled += 1
        except Exception:
            pass

    def record_stage_duration(self, stage_name: str, duration_ms: float) -> None:
        """Records a completed DSP stage execution duration."""
        try:
            with self._lock:
                if stage_name not in self._stage_latencies:
                    # Bound stage dictionary to max 30 unique stages to prevent memory leaks
                    if len(self._stage_latencies) < 30:
                        self._stage_latencies[stage_name] = LatencyTracker()
                    else:
                        return
                self._stage_latencies[stage_name].record(duration_ms)
        except Exception:
            pass

    def get_snapshot(self) -> Dict[str, Any]:
        """
        Produces a bounded, thread-safe JSON snapshot of the in-process metrics.
        Never exposes individual job IDs, request IDs, or raw filenames.
        """
        try:
            with self._lock:
                gauges: Dict[str, Any] = {}
                if self._gauge_provider:
                    try:
                        gauges = self._gauge_provider()
                    except Exception:
                        gauges = {}

                stages_data = {
                    stage: tracker.to_dict()
                    for stage, tracker in self._stage_latencies.items()
                }

                return {
                    "requests": {
                        "total": self._requests_total,
                        "failed": self._requests_failed,
                        "latency_ms": self._request_latency.to_dict(),
                    },
                    "jobs": {
                        "created_total": self._jobs_created,
                        "completed_total": self._jobs_completed,
                        "failed_total": self._jobs_failed,
                        "cancelled_total": self._jobs_cancelled,
                        "queued_current": gauges.get("queued_current", 0),
                        "processing_current": gauges.get("processing_current", 0),
                        "active_total": gauges.get("active_total", 0),
                        "analysis_duration_ms": self._job_analysis_duration.to_dict(),
                    },
                    "workers": {
                        "capacity": gauges.get("worker_capacity", 4),
                        "active": gauges.get("workers_active", 0),
                    },
                    "queue": {
                        "capacity": gauges.get("queue_capacity", 50),
                        "available": gauges.get("queue_available", 50),
                    },
                    "stages": stages_data,
                    "failures": dict(self._failure_counts_by_code),
                }
        except Exception:
            return {"status": "error_retrieving_metrics"}

    def reset(self) -> None:
        """Resets all metric counters and aggregators to zero state (used for testing)."""
        with self._lock:
            self._requests_total = 0
            self._requests_failed = 0
            self._request_latency.reset()
            self._jobs_created = 0
            self._jobs_completed = 0
            self._jobs_failed = 0
            self._jobs_cancelled = 0
            self._job_analysis_duration.reset()
            self._stage_latencies.clear()
            self._failure_counts_by_code.clear()


# Global singleton metrics registry
metrics_registry = MetricsRegistry()
