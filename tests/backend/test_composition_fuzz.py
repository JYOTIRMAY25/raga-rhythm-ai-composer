"""
Adversarial, Property, and Fuzz Tests for Composition Engine and /api/v1/generate Endpoint.
Tests 100+ randomized valid cases and comprehensive invalid edge cases.
"""

from __future__ import annotations

import random
from typing import Any, Dict
import pytest
from fastapi.testclient import TestClient

from backend.app.analysis.raga_detector import RAGA_KNOWLEDGE_BASE
from backend.app.composition.composition_engine import CompositionEngine
from backend.app.composition.composition_models import CompositionRequest, SymbolicComposition
from backend.app.composition.raga_constraints import RagaConstraints
from backend.app.composition.tala_constraints import TalaConstraints
from backend.app.main import app

client = TestClient(app)

ALL_RAGAS = list(RAGA_KNOWLEDGE_BASE.keys())
ALL_TALAS = [
    "teental",
    "ektaal",
    "jhaptaal",
    "rupak",
    "keherwa",
    "dadra",
    "tilwada",
    "jhoomra",
    "addha",
]
ALL_STYLES = ["bandish", "khayal", "alap_gat", "dhrupad"]


class TestCompositionFuzz:
    """Property fuzzing and randomized input testing for the composition engine."""

    def test_randomized_valid_inputs_100_cases(self):
        """
        Executes at least 100 randomized combinations of valid ragas, talas, BPMs,
        durations, styles, creativity scores, and seeds.
        """
        engine = CompositionEngine()
        rng = random.Random(999)

        for case_idx in range(100):
            raga = rng.choice(ALL_RAGAS)
            tala = rng.choice(ALL_TALAS)
            bpm = rng.randint(40, 240)
            duration = rng.randint(15, 180)
            style = rng.choice(ALL_STYLES)
            creativity = rng.randint(0, 100)
            seed = rng.randint(0, 1_000_000)

            req = CompositionRequest(
                raga_id=raga,
                tala_id=tala,
                tempo_bpm=bpm,
                duration_seconds=duration,
                style_id=style,
                creativity_score=creativity,
                seed=seed,
            )

            comp = engine.compose(req)

            # Invariants
            assert comp is not None
            assert comp.raga_id == raga
            assert comp.tempo_bpm == bpm
            assert comp.total_cycles >= 1
            assert len(comp.events) > 0
            assert comp.validation.valid is True
            assert len(comp.validation.diagnostics) == 0 or all(
                d.severity != "error" for d in comp.validation.diagnostics
            )

            # Pydantic serialization invariant
            dumped = comp.model_dump()
            reloaded = SymbolicComposition.model_validate(dumped)
            assert reloaded.composition_id == comp.composition_id

    def test_randomized_api_endpoint_50_cases(self):
        """
        Tests the live FastAPI POST /api/v1/generate endpoint with 50 randomized valid requests.
        """
        rng = random.Random(777)

        for _ in range(50):
            payload = {
                "raga_id": rng.choice(ALL_RAGAS),
                "tala_id": rng.choice(ALL_TALAS),
                "tempo_bpm": rng.randint(40, 240),
                "duration_seconds": rng.randint(15, 120),
                "style_id": rng.choice(ALL_STYLES),
                "creativity_score": rng.randint(0, 100),
                "seed": rng.randint(0, 500_000),
            }

            resp = client.post("/api/v1/generate", json=payload)
            assert resp.status_code == 200, f"Failed for valid payload: {payload}, resp: {resp.text}"
            data = resp.json()
            assert "composition_id" in data
            assert data["validation_result"]["valid"] is True


class TestCompositionAdversarialInvalidCases:
    """Adversarial testing verifying that the API rejects all invalid inputs cleanly with 400/422."""

    def test_unknown_raga_rejected(self):
        resp = client.post("/api/v1/generate", json={"raga_id": "nonexistent_raga_xyz", "tala_id": "teental"})
        assert resp.status_code == 400
        assert "Unknown or unsupported Raga" in resp.json()["detail"]

    def test_unknown_tala_rejected(self):
        resp = client.post("/api/v1/generate", json={"raga_id": "yaman", "tala_id": "fake_tala_999"})
        assert resp.status_code == 400
        assert "Unknown or unsupported Tala" in resp.json()["detail"]

    def test_bpm_zero_rejected(self):
        resp = client.post("/api/v1/generate", json={"raga_id": "yaman", "tala_id": "teental", "tempo_bpm": 0})
        assert resp.status_code == 422

    def test_negative_bpm_rejected(self):
        resp = client.post("/api/v1/generate", json={"raga_id": "yaman", "tala_id": "teental", "tempo_bpm": -50})
        assert resp.status_code == 422

    def test_extremely_high_bpm_rejected(self):
        resp = client.post("/api/v1/generate", json={"raga_id": "yaman", "tala_id": "teental", "tempo_bpm": 600})
        assert resp.status_code == 422

    def test_duration_zero_rejected(self):
        resp = client.post("/api/v1/generate", json={"raga_id": "yaman", "tala_id": "teental", "duration_seconds": 0})
        assert resp.status_code == 422

    def test_negative_duration_rejected(self):
        resp = client.post("/api/v1/generate", json={"raga_id": "yaman", "tala_id": "teental", "duration_seconds": -15})
        assert resp.status_code == 422

    def test_excessive_duration_rejected(self):
        resp = client.post("/api/v1/generate", json={"raga_id": "yaman", "tala_id": "teental", "duration_seconds": 10000})
        assert resp.status_code == 422

    def test_negative_creativity_rejected(self):
        resp = client.post("/api/v1/generate", json={"raga_id": "yaman", "tala_id": "teental", "creativity_score": -10})
        assert resp.status_code == 422

    def test_excessive_creativity_rejected(self):
        resp = client.post("/api/v1/generate", json={"raga_id": "yaman", "tala_id": "teental", "creativity_score": 150})
        assert resp.status_code == 422

    def test_malformed_empty_payload_rejected(self):
        resp = client.post("/api/v1/generate", content="", headers={"Content-Type": "application/json"})
        assert resp.status_code == 422

    def test_malformed_string_types_rejected(self):
        resp = client.post("/api/v1/generate", json={"raga_id": "yaman", "tala_id": "teental", "tempo_bpm": "not-a-number"})
        assert resp.status_code == 422

    def test_no_stack_traces_or_crashes(self):
        # Sending non-JSON garbage
        resp = client.post("/api/v1/generate", content="GARBAGE_PAYLOAD", headers={"Content-Type": "text/plain"})
        assert resp.status_code in [400, 422]
        assert "Traceback" not in resp.text
