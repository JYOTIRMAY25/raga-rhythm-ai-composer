"""
AI Natural-Language Musicological Explanation endpoint.
"""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Body, status

from backend.app.schemas.explanation import GeminiAnalysisExplanation, GeminiExplanationRequest
from backend.app.services.gemini_service import gemini_service

router = APIRouter(tags=["Explanation"])


@router.post(
    "/explain",
    response_model=GeminiAnalysisExplanation,
    status_code=status.HTTP_200_OK,
    summary="Get Natural-Language AI Explanation of Music Analysis",
    description="Generates an educational, structured Indian classical music explanation of machine analysis using Gemini or deterministic fallback.",
)
async def explain_music_analysis(
    payload: Dict[str, Any] = Body(..., description="Analysis data or structured explanation request"),
) -> GeminiAnalysisExplanation:
    """
    Produces structured, validated educational commentary on the given music analysis.
    Gracefully falls back to deterministic rule-based explanation if Gemini is unavailable.
    """
    # Normalize input if nested in AnalysisResponse format
    if "raga" in payload and isinstance(payload["raga"], dict):
        raga_obj = payload.get("raga", {})
        tala_obj = payload.get("tala", {})
        tonic_obj = payload.get("tonic", {})
        rhythm_obj = payload.get("rhythm", {})
        swara_obj = payload.get("swara", {})
        meta_obj = payload.get("audio_metadata", {})

        req = GeminiExplanationRequest(
            raga_name=raga_obj.get("name"),
            raga_id=raga_obj.get("id"),
            thaat=raga_obj.get("thaat"),
            time_of_day=raga_obj.get("time"),
            vadi=raga_obj.get("vadi"),
            samvadi=raga_obj.get("samvadi"),
            aroha=raga_obj.get("aroha", []),
            avaroha=raga_obj.get("avaroha", []),
            raga_confidence=raga_obj.get("confidence"),
            is_ambiguous=raga_obj.get("is_ambiguous", False),
            alternatives=raga_obj.get("alternatives", []),
            tonic_note=tonic_obj.get("note_name") or tonic_obj.get("detected_tonic"),
            tonic_hz=tonic_obj.get("frequency_hz"),
            tonic_confidence=tonic_obj.get("confidence"),
            tala_name=tala_obj.get("name"),
            matras=tala_obj.get("matras"),
            vibhag_structure=tala_obj.get("vibhag_structure"),
            theka=tala_obj.get("theka") if isinstance(tala_obj.get("theka"), str) else " ".join(tala_obj.get("theka", [])),
            bpm=rhythm_obj.get("estimated_bpm") or rhythm_obj.get("bpm"),
            laya=rhythm_obj.get("laya"),
            dominant_swaras=swara_obj.get("dominant_swaras", []),
            pitch_class_distribution=swara_obj.get("pitch_class_distribution", {}),
            warnings=payload.get("warnings", []),
        )
    else:
        req = GeminiExplanationRequest(**payload)

    return gemini_service.explain_analysis(req)
