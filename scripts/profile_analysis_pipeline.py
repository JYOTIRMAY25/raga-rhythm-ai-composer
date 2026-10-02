"""
Comprehensive Analysis Pipeline Profiling and Performance Benchmarking Script.
Measures end-to-end and per-stage latency, peak memory allocation (tracemalloc),
and cProfile function bottlenecks across real Saraga audio recordings and synthetic test inputs.
"""

from __future__ import annotations

import cProfile
import json
import os
import pstats
import platform
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from backend.app.analysis.pipeline import AnalysisPipeline, UnifiedAnalysisResult
from backend.app.analysis.preprocessor import AudioPreprocessor
from backend.app.utils.dataset_adapter import SaragaDatasetAdapter


def get_environment_info() -> Dict[str, Any]:
    """Captures runtime, hardware, and dependency version metadata."""
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
        "numpy_version": np.__version__,
    }


def find_benchmark_audio() -> Optional[Path]:
    """Finds a representative Saraga Hindustani audio track on disk."""
    adapter = SaragaDatasetAdapter()
    for track in adapter.iter_tracks():
        p = Path(track.audio_path)
        if p.exists() and p.stat().st_size > 10000:
            return p
    return None


def run_single_benchmark(
    pipeline: AnalysisPipeline,
    audio_input: Any,
    sr: int = 22050,
) -> Dict[str, Any]:
    """Runs a single instrumented analysis run with memory and stage tracking."""
    tracemalloc.start()
    t_start = time.perf_counter()
    
    if isinstance(audio_input, (str, Path)):
        res: UnifiedAnalysisResult = pipeline.process_file(str(audio_input))
    else:
        res: UnifiedAnalysisResult = pipeline.process_waveform(audio_input, sample_rate=sr)
        
    t_total_ms = (time.perf_counter() - t_start) * 1000.0
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    timings = dict(res.stage_timings_ms)
    timings["total_end_to_end_ms"] = round(t_total_ms, 2)
    timings["peak_memory_mb"] = round(peak_mem / (1024 * 1024), 3)

    return {
        "timings": timings,
        "raga": res.raga.predicted_raga,
        "tala": res.tala.predicted_tala,
        "tonic_hz": res.tonic.frequency_hz,
        "bpm": res.rhythm.estimated_bpm,
        "confidence": res.raga.confidence,
    }


def run_profiling_benchmark(
    num_runs: int = 5,
    duration_sec: float = 10.0,
    audio_path: Optional[Path] = None,
    output_filename: str = "analysis_profiling_optimized.json",
) -> Dict[str, Any]:
    """
    Executes performance benchmarking and cProfile detailed analysis.
    """
    print("=" * 70, flush=True)
    print("STARTING ANALYSIS PIPELINE PROFILING & BENCHMARK", flush=True)
    print("=" * 70, flush=True)

    env_info = get_environment_info()
    print(f"Python: {env_info['python_version'].split()[0]} | Platform: {env_info['platform']}", flush=True)
    print(f"NumPy: {env_info['numpy_version']}", flush=True)

    if audio_path is None or not audio_path.exists():
        audio_path = find_benchmark_audio()

    preprocessor = AudioPreprocessor(max_duration_seconds=3600.0)
    if audio_path and audio_path.exists():
        print(f"Using representative Saraga track: {audio_path.name}", flush=True)
        try:
            import soundfile as sf
            info = sf.info(str(audio_path))
            read_frames = int(min(duration_sec, info.duration) * info.samplerate)
            raw_data, orig_sr = sf.read(str(audio_path), frames=read_frames, dtype="float32", always_2d=True)
            mono_data = preprocessor.to_mono(raw_data)
            resampled_data = preprocessor.resample(mono_data, orig_sr, 22050)
            norm_data, _, _, _ = preprocessor.normalize(resampled_data)
            waveform = norm_data
            sr = 22050
        except Exception as e:
            print(f"Audio loading fallback ({e}), generating synthetic fixture...", flush=True)
            sr = 22050
            t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
            waveform = (
                0.5 * np.sin(2 * np.pi * 140.0 * t) +
                0.3 * np.sin(2 * np.pi * 210.0 * t) +
                0.2 * np.sin(2 * np.pi * 280.0 * t)
            ).astype(np.float32)
    else:
        print("Saraga track not found on disk. Generating synthetic 10s raga-like audio fixture.", flush=True)
        sr = 22050
        t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
        waveform = (
            0.5 * np.sin(2 * np.pi * 140.0 * t) +
            0.3 * np.sin(2 * np.pi * 210.0 * t) +
            0.2 * np.sin(2 * np.pi * 280.0 * t)
        ).astype(np.float32)

    sample_count = len(waveform)
    actual_duration = sample_count / sr
    print(f"Audio properties: Sample Rate = {sr} Hz, Samples = {sample_count}, Duration = {actual_duration:.2f}s\n", flush=True)

    pipeline = AnalysisPipeline()

    # 1. Cold Start Run
    print("--> Measuring Cold Start Run...", flush=True)
    cold_start_res = run_single_benchmark(pipeline, waveform, sr=sr)
    print(f"Cold Start Total: {cold_start_res['timings']['total_end_to_end_ms']} ms (Peak Mem: {cold_start_res['timings']['peak_memory_mb']} MB)", flush=True)

    # 2. Steady State Runs
    print(f"\n--> Measuring {num_runs} Steady-State Runs...", flush=True)
    steady_runs: List[Dict[str, Any]] = []
    for i in range(num_runs):
        run_res = run_single_benchmark(pipeline, waveform, sr=sr)
        steady_runs.append(run_res)
        print(f"  Run {i+1}: Total = {run_res['timings']['total_end_to_end_ms']} ms | "
              f"Pre = {run_res['timings'].get('preprocessing', 0)} ms | "
              f"TonicEst = {run_res['timings'].get('tonic_estimation', 0)} ms | "
              f"Pitch = {run_res['timings'].get('pitch_extraction', 0)} ms | "
              f"TonicRes = {run_res['timings'].get('tonic_resolution', 0)} ms | "
              f"Swara = {run_res['timings'].get('swara_analysis', 0)} ms | "
              f"Raga = {run_res['timings'].get('raga_detection', 0)} ms | "
              f"Rhythm = {run_res['timings'].get('rhythm_analysis', 0)} ms | "
              f"Beat = {run_res['timings'].get('beat_tracking', 0)} ms | "
              f"Tala = {run_res['timings'].get('tala_classification', 0)} ms", flush=True)

    # Calculate statistics per stage
    timing_keys = list(steady_runs[0]["timings"].keys())
    stats: Dict[str, Dict[str, float]] = {}
    for k in timing_keys:
        vals = [r["timings"][k] for r in steady_runs]
        stats[k] = {
            "mean": round(float(np.mean(vals)), 2),
            "median": round(float(np.median(vals)), 2),
            "min": round(float(np.min(vals)), 2),
            "max": round(float(np.max(vals)), 2),
            "std": round(float(np.std(vals)), 2),
        }

    # 3. cProfile Detailed Profiling
    print("\n--> Profiling Detailed Call Graph with cProfile...", flush=True)
    profiler = cProfile.Profile()
    profiler.enable()
    run_single_benchmark(pipeline, waveform, sr=sr)
    profiler.disable()

    stats_stream = pstats.Stats(profiler)
    stats_stream.sort_stats(pstats.SortKey.CUMULATIVE)

    repo_root = Path(__file__).resolve().parent.parent

    def _sanitize(p: str) -> str:
        if not p:
            return ""
        try:
            po = Path(p)
            if po.is_relative_to(repo_root):
                return str(po.relative_to(repo_root)).replace("\\", "/")
        except Exception:
            pass
        if "site-packages" in p:
            idx = p.find("site-packages")
            return p[idx:].replace("\\", "/")
        if "Lib" in p:
            idx = p.find("Lib")
            return p[idx:].replace("\\", "/")
        return os.path.basename(p)

    # Extract top 30 by cumulative time and self time with sanitized paths
    top_cumulative: List[Dict[str, Any]] = []
    for func, (cc, nc, tt, ct, callers) in sorted(stats_stream.stats.items(), key=lambda x: x[1][3], reverse=True)[:30]:
        top_cumulative.append({
            "file": _sanitize(func[0]),
            "line": func[1],
            "function": func[2],
            "ncalls": nc,
            "tottime_ms": round(tt * 1000.0, 2),
            "cumtime_ms": round(ct * 1000.0, 2),
        })

    top_selftime: List[Dict[str, Any]] = []
    for func, (cc, nc, tt, ct, callers) in sorted(stats_stream.stats.items(), key=lambda x: x[1][2], reverse=True)[:30]:
        top_selftime.append({
            "file": _sanitize(func[0]),
            "line": func[1],
            "function": func[2],
            "ncalls": nc,
            "tottime_ms": round(tt * 1000.0, 2),
            "cumtime_ms": round(ct * 1000.0, 2),
        })

    report = {
        "environment": env_info,
        "input_audio": {
            "path": _sanitize(str(audio_path)) if audio_path else "synthetic",
            "sample_rate": sr,
            "samples": sample_count,
            "duration_seconds": actual_duration,
        },
        "cold_start": cold_start_res,
        "steady_state_runs": steady_runs,
        "steady_state_statistics": stats,
        "top_cumulative_functions": top_cumulative,
        "top_selftime_functions": top_selftime,
    }

    # Save artifact
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    out_file = artifacts_dir / output_filename
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nSaved profiling artifact to {out_file}", flush=True)
    print("=" * 70, flush=True)
    return report


if __name__ == "__main__":
    run_profiling_benchmark()
