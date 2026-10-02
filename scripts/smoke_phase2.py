import sys
import os
sys.path.insert(0, os.path.abspath("."))
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.composition.composition_engine import CompositionEngine
from backend.app.services.gemini_service import GeminiService

client = TestClient(app)

def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200, f"Health failed: {resp.text}"
    data = resp.json()
    assert data["status"] == "healthy"
    print("[OK] GET /api/v1/health: OK")

def test_composition_generation():
    # Test generation for Yaman + Teental
    req_body = {
        "raga_id": "yaman",
        "tala_id": "teental",
        "tempo_bpm": 84,
        "tonic_hz": 220.0,
        "seed": 108
    }
    resp = client.post("/api/v1/generate", json=req_body)
    assert resp.status_code == 200, f"Generate failed: {resp.text}"
    data = resp.json()
    assert "composition_id" in data
    assert "symbolic_composition" in data
    sym = data["symbolic_composition"]
    assert sym["raga_name"] == "Yaman"
    assert sym["tala_name"] == "Teental"
    assert data["validation_result"]["valid"] is True
    assert sym["total_cycles"] >= 2
    print(f"[OK] POST /api/v1/generate (Yaman/Teental): OK ({sym['total_cycles']} cycles, {sym['total_matras']} matras, valid={data['validation_result']['valid']})")

    # Test generation across multiple ragas and talas
    test_cases = [
        ("bhairav", "jhaptaal"),
        ("darbari_kanada", "ektaal"),
        ("bhimpalasi", "rupak"),
        ("malkauns", "keherwa"),
        ("todi", "dadra"),
    ]
    for r_id, t_id in test_cases:
        r = client.post("/api/v1/generate", json={"raga_id": r_id, "tala_id": t_id, "seed": 42})
        assert r.status_code == 200, f"Failed for {r_id}/{t_id}: {r.text}"
        res = r.json()
        assert res["validation_result"]["valid"] is True
        print(f"  [OK] {res['symbolic_composition']['raga_name']} in {res['symbolic_composition']['tala_name']}: Valid score generated")

def test_ai_explanation():
    payload = {
        "detected_raga": "Bhairav",
        "raga_confidence": 0.88,
        "thaat": "Bhairav",
        "time": "Morning",
        "mood": "Devotion, Peace",
        "vadi": "d",
        "samvadi": "r",
        "aroha": ["S", "r", "G", "m", "P", "d", "N", "S'"],
        "avaroha": ["S'", "N", "d", "P", "m", "G", "r", "S"],
        "tonic_note": "C#",
        "tonic_hz": 138.59,
        "tonic_confidence": 0.95,
        "bpm": 80.0,
        "tempo_confidence": 0.85,
        "laya": "Madhya",
        "detected_tala": "Teental",
        "matras": 16,
        "tala_confidence": 0.86,
        "dominant_swaras": ["S", "r", "G", "m", "P", "d", "N"],
        "swara_coverage": 0.92,
        "pitch_class_distribution": {"S": 0.28, "r": 0.18, "G": 0.15, "m": 0.12, "P": 0.14, "d": 0.08, "N": 0.05}
    }
    resp = client.post("/api/v1/explain", json=payload)
    assert resp.status_code == 200, f"Explain failed: {resp.text}"
    data = resp.json()
    assert "summary" in data and len(data["summary"]) > 0
    assert "tonic_explanation" in data
    assert "raga_explanation" in data
    assert "swara_explanation" in data
    assert "tala_explanation" in data
    assert isinstance(data["educational_notes"], list)
    print(f"[OK] POST /api/v1/explain: OK (model: {data['model_used']}, available: {data['available']})")

if __name__ == "__main__":
    print("\n================ RUNNING E2E SMOKE TESTS ================")
    test_health()
    test_composition_generation()
    test_ai_explanation()
    print("================ ALL SMOKE TESTS PASSED ================\n")
