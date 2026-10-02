"""
Comprehensive Production Benchmark and Load Testing Suite for RagaRhythm AI.
Measures API latency, memory, throughput, caching performance, concurrency scaling,
and generates artifacts/production_benchmark.json and artifacts/production_benchmark.md.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np

# Add project root to sys.path
sys.path.insert(0, os.path.abspath("."))

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.composition.cache import composition_cache, audio_cache


client = TestClient(app)


def compute_stats(latencies_ms: List[float]) -> Dict[str, float]:
    """Computes mean, median, p95, min, max in milliseconds."""
    arr = np.array(latencies_ms)
    return {
        "mean_ms": round(float(np.mean(arr)), 2),
        "median_ms": round(float(np.median(arr)), 2),
        "p95_ms": round(float(np.percentile(arr, 95)), 2),
        "min_ms": round(float(np.min(arr)), 2),
        "max_ms": round(float(np.max(arr)), 2),
        "samples": len(latencies_ms),
    }


def get_process_memory_mb() -> float:
    """Returns current process resident memory in MB if psutil is available or estimates via sys."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return round(process.memory_info().rss / (1024 * 1024), 2)
    except Exception:
        return 0.0


def benchmark_endpoint(
    method: str,
    url: str,
    json_payload: Optional[Dict[str, Any]] = None,
    iterations: int = 10,
) -> Tuple[Dict[str, float], List[float]]:
    """Runs repeated requests and collects latency statistics."""
    latencies: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        if method.upper() == "GET":
            resp = client.get(url)
        else:
            resp = client.post(url, json=json_payload)
        t1 = time.perf_counter()
        assert resp.status_code == 200, f"Request to {url} failed with {resp.status_code}"
        latencies.append((t1 - t0) * 1000.0)
    return compute_stats(latencies), latencies


def run_concurrency_test(num_workers: int = 5, duration_sec: int = 20) -> Dict[str, Any]:
    """Executes concurrent composition generation requests across multiple threads."""
    payloads = [
        {"raga_id": "yaman", "tala_id": "teental", "duration_seconds": duration_sec, "seed": 42 + i}
        for i in range(num_workers)
    ]

    def _worker(payload: Dict[str, Any]) -> Tuple[int, float, int]:
        t0 = time.perf_counter()
        resp = client.post("/api/v1/generate", json=payload)
        t1 = time.perf_counter()
        return resp.status_code, (t1 - t0) * 1000.0, len(resp.content)

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        results = list(executor.map(_worker, payloads))
    total_time_ms = (time.perf_counter() - t_start) * 1000.0

    success_count = sum(1 for status, _, _ in results if status == 200)
    latencies = [lat for _, lat, _ in results]

    return {
        "concurrency_level": num_workers,
        "total_requests": num_workers,
        "success_rate": round((success_count / num_workers) * 100.0, 1),
        "total_time_ms": round(total_time_ms, 2),
        "stats": compute_stats(latencies),
    }


def main():
    print("==================================================================")
    print("STARTING PRODUCTION BENCHMARK & LOAD TESTS")
    print("==================================================================")

    initial_memory = get_process_memory_mb()
    print(f"Initial Memory Usage: {initial_memory} MB")

    # 1. Benchmark API Endpoints
    print("\n--- 1. Benchmarking API Endpoints ---")
    health_stats, _ = benchmark_endpoint("GET", "/api/v1/health", iterations=20)
    print(f"GET /health: {health_stats}")

    ragas_stats, _ = benchmark_endpoint("GET", "/api/v1/ragas", iterations=10)
    print(f"GET /ragas: {ragas_stats}")

    talas_stats, _ = benchmark_endpoint("GET", "/api/v1/talas", iterations=10)
    print(f"GET /talas: {talas_stats}")

    # 2. Benchmark Composition Generation (Uncached & Cached)
    print("\n--- 2. Benchmarking Composition Generation ---")
    composition_cache.clear()
    audio_cache.clear()

    durations = [("small_20s", 20), ("normal_45s", 45), ("long_60s", 60), ("max_300s", 300)]
    composition_benchmarks = {}

    for label, dur in durations:
        payload = {"raga_id": "yaman", "tala_id": "teental", "duration_seconds": dur, "seed": 108}
        
        # Uncached run
        composition_cache.clear()
        t0 = time.perf_counter()
        resp = client.post("/api/v1/generate", json=payload)
        t_uncached_ms = (time.perf_counter() - t0) * 1000.0
        assert resp.status_code == 200

        # Cached runs
        cached_stats, _ = benchmark_endpoint("POST", "/api/v1/generate", json_payload=payload, iterations=10)

        composition_benchmarks[label] = {
            "duration_seconds": dur,
            "uncached_ms": round(t_uncached_ms, 2),
            "cached_stats": cached_stats,
        }
        print(f"Generate ({label}): Uncached = {t_uncached_ms:.2f}ms | Cached Mean = {cached_stats['mean_ms']}ms")

    # 3. Benchmark WAV Audio Synthesis (Uncached & Cached)
    print("\n--- 3. Benchmarking Audio WAV Rendering ---")
    audio_benchmarks = {}

    for label, dur in durations:
        payload = {
            "raga_id": "yaman",
            "tala_id": "teental",
            "duration_seconds": dur,
            "seed": 108,
            "tuning_mode": "raga_aware",
            "timbre": "flute",
        }

        # Uncached render
        audio_cache.clear()
        t0 = time.perf_counter()
        wav_resp = client.post("/api/v1/generate/wav", json=payload)
        t_render_uncached_ms = (time.perf_counter() - t0) * 1000.0
        assert wav_resp.status_code == 200
        wav_size_bytes = len(wav_resp.content)

        # Cached renders
        cached_render_stats, _ = benchmark_endpoint("POST", "/api/v1/generate/wav", json_payload=payload, iterations=5)

        audio_benchmarks[label] = {
            "duration_seconds": dur,
            "wav_size_bytes": wav_size_bytes,
            "uncached_ms": round(t_render_uncached_ms, 2),
            "cached_stats": cached_render_stats,
        }
        print(f"Render WAV ({label}): Size = {wav_size_bytes}B | Uncached = {t_render_uncached_ms:.2f}ms | Cached = {cached_render_stats['mean_ms']}ms")

    # 4. Concurrency Testing
    print("\n--- 4. Concurrency Scaling Tests ---")
    concurrency_results = []
    for concurrency in [2, 5, 10]:
        res = run_concurrency_test(num_workers=concurrency, duration_sec=20)
        concurrency_results.append(res)
        print(f"Concurrency {concurrency}: Success = {res['success_rate']}% | Mean Latency = {res['stats']['mean_ms']}ms | Total = {res['total_time_ms']}ms")

    # 5. Frontend Build Size Inspection
    dist_path = Path("dist")
    frontend_size_kb = 0.0
    if dist_path.exists():
        total_b = sum(f.stat().st_size for f in dist_path.glob("**/*") if f.is_file())
        frontend_size_kb = round(total_b / 1024.0, 2)
        print(f"\nFrontend Production Bundle Size: {frontend_size_kb} KB")

    final_memory = get_process_memory_mb()
    print(f"Final Memory Usage: {final_memory} MB (Delta: {round(final_memory - initial_memory, 2)} MB)")

    # 6. Save JSON & Markdown Artifacts
    benchmark_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "endpoints": {
            "health": health_stats,
            "ragas": ragas_stats,
            "talas": talas_stats,
        },
        "composition_generation": composition_benchmarks,
        "audio_synthesis": audio_benchmarks,
        "concurrency_scaling": concurrency_results,
        "frontend_bundle_size_kb": frontend_size_kb,
        "memory_mb": {
            "initial": initial_memory,
            "final": final_memory,
            "delta": round(final_memory - initial_memory, 2),
        },
        "cache_stats": {
            "composition": composition_cache.stats(),
            "audio": audio_cache.stats(),
        }
    }

    os.makedirs("artifacts", exist_ok=True)
    with open("artifacts/production_benchmark.json", "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)

    # Markdown report
    md_content = f"""# Production Performance & Load Benchmark Report

**Generated**: {benchmark_data['timestamp']}  
**Architecture**: FastAPI / Python 3.11 / Librosa / NumPy / Vite React Frontend  

---

## 1. API Endpoint Latencies

| Endpoint | Samples | Mean (ms) | Median (ms) | p95 (ms) | Min (ms) | Max (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /health` | {health_stats['samples']} | {health_stats['mean_ms']} | {health_stats['median_ms']} | {health_stats['p95_ms']} | {health_stats['min_ms']} | {health_stats['max_ms']} |
| `GET /ragas` | {ragas_stats['samples']} | {ragas_stats['mean_ms']} | {ragas_stats['median_ms']} | {ragas_stats['p95_ms']} | {ragas_stats['min_ms']} | {ragas_stats['max_ms']} |
| `GET /talas` | {talas_stats['samples']} | {talas_stats['mean_ms']} | {talas_stats['median_ms']} | {talas_stats['p95_ms']} | {talas_stats['min_ms']} | {talas_stats['max_ms']} |

---

## 2. Algorithmic Composition Generation

| Composition Tier | Duration | Uncached (ms) | Cached Mean (ms) | Cached p95 (ms) |
| :--- | :--- | :--- | :--- | :--- |
| **Small (20s)** | 20s | {composition_benchmarks['small_20s']['uncached_ms']} | {composition_benchmarks['small_20s']['cached_stats']['mean_ms']} | {composition_benchmarks['small_20s']['cached_stats']['p95_ms']} |
| **Normal (45s)** | 45s | {composition_benchmarks['normal_45s']['uncached_ms']} | {composition_benchmarks['normal_45s']['cached_stats']['mean_ms']} | {composition_benchmarks['normal_45s']['cached_stats']['p95_ms']} |
| **Long (60s)** | 60s | {composition_benchmarks['long_60s']['uncached_ms']} | {composition_benchmarks['long_60s']['cached_stats']['mean_ms']} | {composition_benchmarks['long_60s']['cached_stats']['p95_ms']} |
| **Max Cap (300s)** | 300s | {composition_benchmarks['max_300s']['uncached_ms']} | {composition_benchmarks['max_300s']['cached_stats']['mean_ms']} | {composition_benchmarks['max_300s']['cached_stats']['p95_ms']} |

---

## 3. Audio WAV Synthesis & Rendering

| Tier | Duration | WAV Size | Uncached Render (ms) | Cached Render (ms) |
| :--- | :--- | :--- | :--- | :--- |
| **Small (20s)** | 20s | {audio_benchmarks['small_20s']['wav_size_bytes']:,} B | {audio_benchmarks['small_20s']['uncached_ms']} | {audio_benchmarks['small_20s']['cached_stats']['mean_ms']} |
| **Normal (45s)** | 45s | {audio_benchmarks['normal_45s']['wav_size_bytes']:,} B | {audio_benchmarks['normal_45s']['uncached_ms']} | {audio_benchmarks['normal_45s']['cached_stats']['mean_ms']} |
| **Long (60s)** | 60s | {audio_benchmarks['long_60s']['wav_size_bytes']:,} B | {audio_benchmarks['long_60s']['uncached_ms']} | {audio_benchmarks['long_60s']['cached_stats']['mean_ms']} |
| **Max Cap (300s)** | 300s | {audio_benchmarks['max_300s']['wav_size_bytes']:,} B | {audio_benchmarks['max_300s']['uncached_ms']} | {audio_benchmarks['max_300s']['cached_stats']['mean_ms']} |

---

## 4. Concurrency & Throughput Scaling

| Concurrency Level | Success Rate | Total Time (ms) | Mean Latency (ms) | p95 Latency (ms) |
| :--- | :--- | :--- | :--- | :--- |
"""
    for res in concurrency_results:
        md_content += f"| **{res['concurrency_level']} Simultaneous** | {res['success_rate']}% | {res['total_time_ms']} | {res['stats']['mean_ms']} | {res['stats']['p95_ms']} |\n"

    md_content += f"""
---

## 5. Memory & Asset Sizes

- **Frontend Bundle Size**: {frontend_size_kb} KB
- **Process Memory Delta**: {benchmark_data['memory_mb']['delta']} MB
- **Composition Cache Entries**: {composition_cache.stats()['entries']} / {composition_cache.stats()['max_entries']}
- **Audio Cache Entries**: {audio_cache.stats()['entries']} / {audio_cache.stats()['max_entries']}
"""

    with open("artifacts/production_benchmark.md", "w", encoding="utf-8") as f:
        f.write(md_content)

    print("\nBENCHMARK ARTIFACTS GENERATED:")
    print("  - artifacts/production_benchmark.json")
    print("  - artifacts/production_benchmark.md")
    print("==================================================================")


if __name__ == "__main__":
    main()
