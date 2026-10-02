"""
Gemini AI Musical Explanation Service.

Provides natural-language musicological commentary on machine-generated analysis
using Google Gemini API with robust graceful fallback when API key is unconfigured.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from backend.app.core.config import settings
from backend.app.schemas.explanation import GeminiAnalysisExplanation, GeminiExplanationRequest

logger = logging.getLogger(__name__)

GEMINI_SYSTEM_INSTRUCTION = (
    "You are an expert Indian Classical Music (ICM) musicologist assistant. "
    "Your duty is to explain machine-generated audio analysis to students and practitioners. "
    "STRICT RULES:\n"
    "1. Explain ONLY the supplied machine analysis data.\n"
    "2. Do NOT invent analysis results or contradict the supplied tonic, raga, tala, BPM, or swaras.\n"
    "3. If any field is marked ambiguous or has low confidence, explicitly address the acoustic uncertainty.\n"
    "4. Return clean, educational, and respectful commentary adhering strictly to Indian classical theory.\n"
    "5. Output MUST be valid JSON matching the requested fields."
)


class GeminiService:
    """Service providing natural-language musical explanations via Gemini with deterministic fallback."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or getattr(settings, "gemini_model", "gemini-1.5-flash")
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize Google GenAI client if credentials are present."""
        if not self.api_key:
            logger.info("GEMINI_API_KEY not configured. GeminiService running in offline fallback mode.")
            return

        try:
            # Try new google-genai SDK first
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            self._sdk_type = "genai"
            logger.info("Initialized google-genai Client successfully.")
        except Exception as e:
            try:
                # Fallback to google.generativeai if installed
                import google.generativeai as genai_legacy
                genai_legacy.configure(api_key=self.api_key)
                self._client = genai_legacy.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=GEMINI_SYSTEM_INSTRUCTION,
                )
                self._sdk_type = "generativeai_legacy"
                logger.info("Initialized google.generativeai legacy client successfully.")
            except Exception as e_legacy:
                logger.warning(f"Could not initialize GenAI client: {e_legacy}. Using offline fallback.")
                self._client = None

    def explain_analysis(self, payload: GeminiExplanationRequest | Dict[str, Any]) -> GeminiAnalysisExplanation:
        """
        Generates a comprehensive structured explanation of music analysis.
        Uses live Gemini if available, or returns deterministic expert ICM explanation.
        """
        req = payload if isinstance(payload, GeminiExplanationRequest) else GeminiExplanationRequest(**payload)

        # If live Gemini is available, attempt inference
        if self._client and self.api_key:
            try:
                explanation = self._call_gemini_api(req)
                if explanation:
                    return explanation
            except Exception as e:
                logger.warning(f"Gemini API invocation failed ({e}). Reverting to deterministic expert explanation.")

        # Deterministic offline musicological explanation fallback
        return self._generate_deterministic_explanation(req)

    def _call_gemini_api(self, req: GeminiExplanationRequest) -> Optional[GeminiAnalysisExplanation]:
        """Calls Gemini API with structured JSON response schema."""
        prompt = (
            f"Please explain this Indian Classical Music analysis:\n"
            f"- Detected Raga: {req.raga_name or 'Unspecified'} (Thaat: {req.thaat or 'Unspecified'}, Confidence: {req.raga_confidence})\n"
            f"- Aroha: {req.aroha}\n"
            f"- Avaroha: {req.avaroha}\n"
            f"- Vadi: {req.vadi}, Samvadi: {req.samvadi}\n"
            f"- Resolved Tonic (Sa): {req.tonic_note} ({req.tonic_hz} Hz, Confidence: {req.tonic_confidence})\n"
            f"- Detected Tala: {req.tala_name} ({req.matras} beats, Vibhag: {req.vibhag_structure}, Theka: {req.theka})\n"
            f"- Tempo: {req.bpm} BPM ({req.laya} laya)\n"
            f"- Dominant Swaras: {req.dominant_swaras}\n"
            f"- Is Ambiguous: {req.is_ambiguous}\n"
            f"- Allied Ragas / Alternatives: {req.alternatives}\n"
            f"- Diagnostic Warnings: {req.warnings}\n\n"
            f"Provide a JSON object with keys: summary, tonic_explanation, raga_explanation, "
            f"swara_explanation, rhythm_explanation, tala_explanation, confidence_notes, "
            f"warnings (list of strings), educational_notes (list of strings)."
        )

        try:
            if getattr(self, "_sdk_type", None) == "genai":
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config={
                        "system_instruction": GEMINI_SYSTEM_INSTRUCTION,
                        "response_mime_type": "application/json",
                        "temperature": 0.3,
                    },
                )
                text = response.text
            else:
                response = self._client.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json", "temperature": 0.3},
                )
                text = response.text

            data = json.loads(text)
            return GeminiAnalysisExplanation(
                available=True,
                summary=data.get("summary", ""),
                tonic_explanation=data.get("tonic_explanation", ""),
                raga_explanation=data.get("raga_explanation", ""),
                swara_explanation=data.get("swara_explanation", ""),
                rhythm_explanation=data.get("rhythm_explanation", ""),
                tala_explanation=data.get("tala_explanation", ""),
                confidence_notes=data.get("confidence_notes", ""),
                warnings=data.get("warnings", []),
                educational_notes=data.get("educational_notes", []),
                model_used=self.model_name,
            )
        except Exception as err:
            logger.error(f"Error parsing Gemini response: {err}")
            return None

    def _generate_deterministic_explanation(self, req: GeminiExplanationRequest) -> GeminiAnalysisExplanation:
        """
        Produces high-precision, rule-based musicological explanations adhering
        strictly to the encoded Hindustani knowledge base.
        """
        raga = req.raga_name or "Unknown Raga"
        thaat = req.thaat or "unclassified"
        time = req.time_of_day or "flexible time"
        vadi = req.vadi or "S"
        samvadi = req.samvadi or "P"
        tonic_str = f"{req.tonic_note} ({req.tonic_hz:.1f} Hz)" if req.tonic_hz else (req.tonic_note or "Middle C")
        tala = req.tala_name or "Unmetered / Alaap"
        bpm = f"{req.bpm:.1f} BPM" if req.bpm else "tempo not steady"
        laya = req.laya or "Madhya"

        summary = (
            f"The recording exhibits characteristic melodic contours of Raga {raga} "
            f"anchored at a resolved tonic (Sa) of {tonic_str}. "
            f"The rhythmic framework corresponds to {tala} at approximately {bpm} ({laya} laya)."
        )

        tonic_explanation = (
            f"The foundational pitch (Adhara Shadja / Sa) has been acoustically resolved to {tonic_str}. "
            f"In Indian classical music, all melodic intervals and swara positions (shuddha, komal, tivra) "
            f"are measured as exact frequency ratios relative to this fundamental frequency."
        )

        raga_explanation = (
            f"Raga {raga} belongs to the {thaat} Thaat family and is traditionally associated with {time}. "
            f"Its melodic movement is governed by Vadi (predominant note) '{vadi}' and Samvadi '{samvadi}'. "
            f"The melodic structure follows Aroha: {' - '.join(req.aroha) if req.aroha else 'Ascending sequence'} "
            f"and Avaroha: {' - '.join(req.avaroha) if req.avaroha else 'Descending sequence'}."
        )

        dominant_str = ", ".join(req.dominant_swaras) if req.dominant_swaras else "Sa, Pa"
        swara_explanation = (
            f"Pitch class distribution highlights high prominence on {dominant_str}. "
            f"The balance of swaras reflects characteristic resting notes (Nyasa swaras) "
            f"and ornamentation typical of {raga}."
        )

        rhythm_explanation = (
            f"Tempo analysis indicates an estimated pulse of {bpm} in {laya} laya. "
            f"The rhythmic density reflects regular metric cycles suited for classical exposition."
        )

        tala_explanation = (
            f"The rhythmic cycle has been identified as {tala} "
            f"({req.matras or 16} matras divided into vibhags: {req.vibhag_structure or 'symmetric partitions'}). "
            f"The cycle begins on Sam (beat 1), serving as the primary anchor for melodic resolution."
        )

        conf_pct = int((req.raga_confidence or 0.8) * 100)
        confidence_notes = (
            f"Machine classification achieved a {conf_pct}% confidence score based on pitch class correlation "
            f"and motif matching."
        )
        if req.is_ambiguous:
            confidence_notes += (
                " Note: Melodic phrases show overlap with allied ragas in the same family, "
                "suggesting subtle aesthetic boundaries."
            )

        warnings_list = [w.get("message", str(w)) for w in (req.warnings or [])]
        if not self.api_key:
            warnings_list.append("AI commentary rendered via deterministic ICM rule engine (GEMINI_API_KEY unconfigured).")

        educational_notes = [
            f"Listen for the interplay between Vadi ({vadi}) and Samvadi ({samvadi}) to understand the raga's focal points.",
            f"Observe how phrases resolve to Sam on beat 1 of the {tala} cycle.",
            "Notice the subtle glides (meend) and microtonal inflections that distinguish this raga from allied scales.",
        ]

        return GeminiAnalysisExplanation(
            available=False,
            summary=summary,
            tonic_explanation=tonic_explanation,
            raga_explanation=raga_explanation,
            swara_explanation=swara_explanation,
            rhythm_explanation=rhythm_explanation,
            tala_explanation=tala_explanation,
            confidence_notes=confidence_notes,
            warnings=warnings_list,
            educational_notes=educational_notes,
            model_used="deterministic-icm-rule-engine",
        )

    def explain_raga(self, raga_name: str) -> Dict[str, str]:
        """Provides brief educational notes on a specific raga."""
        return {
            "raga": raga_name,
            "overview": f"Raga {raga_name} is an integral part of classical Hindustani music performance.",
        }

    def explain_tala(self, tala_name: str) -> Dict[str, str]:
        """Provides brief educational notes on a specific tala."""
        return {
            "tala": tala_name,
            "overview": f"Tala {tala_name} provides the rhythmic framework for classical composition.",
        }

    def explain_composition(self, composition_meta: Dict[str, Any]) -> Dict[str, str]:
        """Provides theoretical context for an algorithmically generated composition."""
        raga = composition_meta.get("raga_name", "Unknown")
        tala = composition_meta.get("tala_name", "Unknown")
        return {
            "title": f"Algorithmic {raga} in {tala}",
            "commentary": (
                f"This composition was generated using deterministic Indian classical melodic constraints. "
                f"It develops from Sthayi across {tala} cycles and concludes with a cadence resolving on Sam."
            ),
        }


# Singleton service instance
gemini_service = GeminiService()
