"""
Deterministic, Bounded LRU Cache for Symbolic Compositions and Synthesized Audio WAVs.
Thread-safe, memory-bounded, with explicit renderer versioning and cache invalidation.
"""

from __future__ import annotations

import hashlib
import json
import sys
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from backend.app.composition.composition_models import (
    CompositionRequest,
    CompositionResponse,
    SymbolicComposition,
)

AUDIO_RENDERER_VERSION: str = "1.0"


def compute_composition_cache_key(req: CompositionRequest) -> str:
    """
    Computes a deterministic SHA-256 cache key based on all output-affecting parameters.
    """
    payload = {
        "raga_id": req.raga_id.lower().strip().replace(" ", "_").replace("-", "_"),
        "tala_id": req.tala_id.lower().strip().replace(" ", "_").replace("-", "_"),
        "tonic": req.tonic or "C",
        "tonic_hz": req.tonic_hz or 0.0,
        "tempo_bpm": req.tempo_bpm,
        "duration_seconds": req.duration_seconds,
        "style_id": req.style_id or "bandish",
        "creativity_score": req.creativity_score,
        "seed": req.seed if req.seed is not None else 42,
        "tuning_mode": req.tuning_mode or "canonical",
        "timbre": req.timbre or "ensemble",
    }
    serialized = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_audio_cache_key(
    composition_id: str,
    raga_id: str,
    tala_id: str,
    seed: int,
    tempo_bpm: int,
    duration_seconds: float,
    tuning_mode: str = "canonical",
    timbre: str = "ensemble",
    renderer_version: str = AUDIO_RENDERER_VERSION,
) -> str:
    """
    Computes a deterministic SHA-256 cache key for synthesized WAV binary streams.
    Explicitly includes renderer_version to invalidate cache upon DSP/timbre algorithm upgrades.
    """
    payload = {
        "composition_id": composition_id,
        "raga_id": raga_id,
        "tala_id": tala_id,
        "seed": seed,
        "tempo_bpm": tempo_bpm,
        "duration_seconds": round(duration_seconds, 2),
        "tuning_mode": tuning_mode,
        "timbre": timbre,
        "renderer_version": renderer_version,
    }
    serialized = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class BoundedLRUCache:
    """
    Thread-safe, memory-bounded Least Recently Used (LRU) cache with entry count
    and approximate memory limits.
    """

    def __init__(self, max_entries: int = 250, max_memory_bytes: int = 50 * 1024 * 1024):
        self.max_entries = max_entries
        self.max_memory_bytes = max_memory_bytes
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._approx_bytes: int = 0
        self._lock = threading.Lock()
        self.hits: int = 0
        self.misses: int = 0

    def _estimate_size(self, value: Any) -> int:
        if isinstance(value, bytes):
            return len(value)
        if isinstance(value, str):
            return len(value.encode("utf-8"))
        if hasattr(value, "model_dump_json"):
            return len(value.model_dump_json().encode("utf-8"))
        return sys.getsizeof(value)

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None
            self._cache.move_to_end(key)
            self.hits += 1
            return self._cache[key]

    def set(self, key: str, value: Any) -> None:
        if value is None:
            return

        with self._lock:
            val_size = self._estimate_size(value)
            if key in self._cache:
                old_size = self._estimate_size(self._cache[key])
                self._approx_bytes -= old_size
                del self._cache[key]

            # Evict if exceeding max_entries or max_memory_bytes
            while (
                self._cache
                and (len(self._cache) >= self.max_entries or self._approx_bytes + val_size > self.max_memory_bytes)
            ):
                old_k, old_v = self._cache.popitem(last=False)
                self._approx_bytes -= self._estimate_size(old_v)

            self._cache[key] = value
            self._approx_bytes += val_size

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._approx_bytes = 0
            self.hits = 0
            self.misses = 0

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            hit_ratio = (self.hits / total) if total > 0 else 0.0
            return {
                "entries": len(self._cache),
                "max_entries": self.max_entries,
                "memory_bytes": self._approx_bytes,
                "max_memory_bytes": self.max_memory_bytes,
                "hits": self.hits,
                "misses": self.misses,
                "hit_ratio": round(hit_ratio, 3),
            }


# Global Singletons
composition_cache = BoundedLRUCache(max_entries=300, max_memory_bytes=25 * 1024 * 1024)
audio_cache = BoundedLRUCache(max_entries=100, max_memory_bytes=75 * 1024 * 1024)
