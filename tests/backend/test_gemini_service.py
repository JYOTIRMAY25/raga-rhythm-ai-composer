"""
Unit tests for Gemini AI Explanation Service.
"""

import unittest
from unittest.mock import MagicMock, patch

from backend.app.schemas.explanation import GeminiAnalysisExplanation, GeminiExplanationRequest
from backend.app.services.gemini_service import GeminiService


class TestGeminiService(unittest.TestCase):
    """Test suite for Gemini AI explanation service and fallback handling."""

    def setUp(self):
        self.sample_request = GeminiExplanationRequest(
            raga_name="Yaman",
            thaat="Kalyan",
            vadi="G",
            samvadi="N",
            aroha=["N.", "R", "G", "M", "D", "N", "S'"],
            avaroha=["S'", "N", "D", "P", "M", "G", "R", "S"],
            tonic_note="C#",
            tonic_hz=138.59,
            tonic_confidence=0.95,
            tala_name="Teental",
            matras=16,
            vibhag_structure="4+4+4+4",
            bpm=84.0,
            laya="Madhya",
            dominant_swaras=["G", "N", "P"],
            raga_confidence=0.92,
        )

    def test_missing_api_key_returns_deterministic_explanation(self):
        """When GEMINI_API_KEY is not set, service returns structured fallback commentary."""
        service = GeminiService(api_key=None)
        result = service.explain_analysis(self.sample_request)

        self.assertIsInstance(result, GeminiAnalysisExplanation)
        self.assertFalse(result.available)
        self.assertIn("Yaman", result.summary)
        self.assertIn("C#", result.tonic_explanation)
        self.assertIn("Teental", result.tala_explanation)
        self.assertGreater(len(result.educational_notes), 0)
        self.assertEqual(result.model_used, "deterministic-icm-rule-engine")

    def test_mocked_gemini_success_response(self):
        """When Gemini API responds with structured JSON, service formats it properly."""
        service = GeminiService(api_key="mock-api-key-test")
        
        mock_json_response = (
            '{"summary": "A quintessential evening Yaman presentation.", '
            '"tonic_explanation": "Sa anchored at C#.", '
            '"raga_explanation": "Kalyan thaat raga characterized by Tivra Ma.", '
            '"swara_explanation": "Prominent Ga and Ni.", '
            '"rhythm_explanation": "Steady 84 BPM tempo.", '
            '"tala_explanation": "16 beat Teental cycle.", '
            '"confidence_notes": "High confidence 92%.", '
            '"warnings": [], "educational_notes": ["Notice the Kalyan movement."]}'
        )

        with patch.object(service, "_call_gemini_api") as mock_call:
            mock_call.return_value = GeminiAnalysisExplanation(
                available=True,
                summary="A quintessential evening Yaman presentation.",
                tonic_explanation="Sa anchored at C#.",
                raga_explanation="Kalyan thaat raga characterized by Tivra Ma.",
                swara_explanation="Prominent Ga and Ni.",
                rhythm_explanation="Steady 84 BPM tempo.",
                tala_explanation="16 beat Teental cycle.",
                confidence_notes="High confidence 92%.",
                warnings=[],
                educational_notes=["Notice the Kalyan movement."],
                model_used="gemini-1.5-flash",
            )
            result = service.explain_analysis(self.sample_request)

            self.assertTrue(result.available)
            self.assertEqual(result.model_used, "gemini-1.5-flash")
            self.assertIn("Yaman", result.summary)

    def test_gemini_api_failure_graceful_fallback(self):
        """When Gemini call throws exception (timeout/network error), reverts to deterministic explanation."""
        service = GeminiService(api_key="mock-api-key-test")

        with patch.object(service, "_call_gemini_api", side_effect=RuntimeError("Network timeout")):
            result = service.explain_analysis(self.sample_request)

            self.assertIsInstance(result, GeminiAnalysisExplanation)
            self.assertFalse(result.available)
            self.assertIn("Yaman", result.summary)


if __name__ == "__main__":
    unittest.main()
