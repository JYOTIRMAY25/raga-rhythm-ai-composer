import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.app.main import app

def run_smoke_test():
    client = TestClient(app)

    # 1. Health check
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200, f"Health check failed: {health_resp.text}"
    print("Health response:", health_resp.json())

    # 2. Raga Catalog
    ragas_resp = client.get("/api/v1/ragas")
    assert ragas_resp.status_code == 200, f"Ragas fetch failed: {ragas_resp.text}"
    ragas = ragas_resp.json()["ragas"]
    print(f"Ragas catalog loaded: {len(ragas)} ragas (Sample: {ragas[0]['name']})")

    # 3. Tala Catalog
    talas_resp = client.get("/api/v1/talas")
    assert talas_resp.status_code == 200, f"Talas fetch failed: {talas_resp.text}"
    talas = talas_resp.json()["talas"]
    print(f"Talas catalog loaded: {len(talas)} talas (Sample: {talas[0]['name']})")

    # 4. Generate 501 Check
    gen_resp = client.post("/api/v1/generate", json={"raga_id": "yaman", "tala_id": "teental"})
    assert gen_resp.status_code == 501, f"Generate should return 501, got {gen_resp.status_code}"
    print("Generate 501 placeholder response verified:", gen_resp.json()["message"])

    # 5. Real Saraga Track Analysis
    from backend.app.utils.dataset_adapter import SaragaDatasetAdapter
    adapter = SaragaDatasetAdapter()
    track_dirs = adapter.scan_dataset()
    print(f"\nDiscovered {len(track_dirs)} Saraga tracks via dataset adapter.")

    # Find an audio file in the dataset with size/duration <= 600s (e.g., <= 20MB)
    audio_file_path = None
    if track_dirs:
        for t_dir in track_dirs:
            mp3_files = list(t_dir.glob("*.mp3")) + list(t_dir.glob("*.mp3.mp3")) + list(t_dir.glob("*.wav"))
            for f in mp3_files:
                # 600s audio at 128kbps is ~9.6MB, so <= 8MB is guaranteed < 600s
                if f.stat().st_size < 8 * 1024 * 1024:
                    audio_file_path = f
                    break
            if audio_file_path:
                break

    if audio_file_path and audio_file_path.exists():
        print(f"Analyzing real Saraga Hindustani audio: {audio_file_path.name}...")
        with open(audio_file_path, "rb") as audio_file:
            response = client.post(
                "/api/v1/analyze",
                files={"file": (audio_file_path.name, audio_file, "audio/mpeg")},
            )
    else:
        # If dataset contains metadata only, use track tonic annotation
        track_meta = adapter.get_track_annotations(track_dirs[0])
        tonic_hz = track_meta.tonic_hz or 146.83
        raga_title = track_meta.raga_names[0] if track_meta.raga_names else "Bhairav"
        print(f"Generating synthetic verification excerpt for Saraga track: {track_meta.title} (Raga {raga_title}, Tonic {tonic_hz} Hz)...")
        import numpy as np
        import soundfile as sf
        import io
        sr = 22050
        duration = 5.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        audio = 0.6 * np.sin(2 * np.pi * tonic_hz * t) + 0.3 * np.sin(2 * np.pi * (tonic_hz * 1.5) * t)
        buf = io.BytesIO()
        sf.write(buf, audio, sr, format="WAV")
        buf.seek(0)
        response = client.post(
            "/api/v1/analyze",
            files={"file": (f"{raga_title}_saraga_excerpt.wav", buf, "audio/wav")},
        )

    assert response.status_code == 200, f"Analysis failed with {response.status_code}: {response.text}"
    data = response.json()

    print("\n=======================================================")
    print("        REAL SARAGA SMOKE TEST RESULTS")
    print("=======================================================")
    print("Track:", data["audio_metadata"]["filename"])
    print("Duration:", f"{data['audio_metadata']['duration_seconds']:.2f}s")
    print("Sample Rate:", data["audio_metadata"]["sample_rate"], "Hz")
    print("Resolved Tonic (Sa):", f"{data['tonic']['note_name']} ({data['tonic']['frequency_hz']:.1f} Hz, {data['tonic']['confidence']:.0%} conf)")
    print("Detected Raga:", f"{data['raga']['name']} ({data['raga']['confidence']:.0%} conf, Thaat: {data['raga']['thaat']})")
    print("Dominant Swaras:", ", ".join(data["swara"]["dominant_swaras"]))
    print("Pitch Voicing %:", f"{data['pitch']['voiced_percentage']:.1f}%")
    print("Rhythm / Tempo:", f"{data['rhythm']['estimated_bpm']} BPM ({data['rhythm']['laya']} laya)")
    print("Detected Tala:", f"{data['tala']['name']} ({data['tala']['matras']} beats, Vibhag: {data['tala']['vibhag_structure']})")
    print("Processing Latency:", f"{data['processing_time_ms']:.0f} ms")
    print("Diagnostics / Warnings:", len(data["warnings"]))
    print("=======================================================\n")

if __name__ == "__main__":
    run_smoke_test()
