"""
Algorithmic Composition Package for Indian Classical Music.
"""

from backend.app.composition.audio_renderer import AudioRenderer, audio_renderer
from backend.app.composition.composition_engine import CompositionEngine, composition_engine
from backend.app.composition.composition_models import (
    CompositionCycle,
    CompositionRequest,
    CompositionResponse,
    SwaraEvent,
    SymbolicComposition,
    ValidationDiagnostic,
    ValidationResult,
)
from backend.app.composition.composition_validator import CompositionValidator
from backend.app.composition.expression import ExpressionController, expression_controller
from backend.app.composition.melody_generator import MelodyGenerator
from backend.app.composition.raga_constraints import RagaConstraints
from backend.app.composition.rhythm_generator import RhythmGenerator
from backend.app.composition.shruti import (
    IntonationProfile,
    ShrutiMapper,
    ShrutiPitch,
    shruti_mapper,
)
from backend.app.composition.tala_constraints import TalaConstraints
from backend.app.composition.timbre import TimbralSynthesizer, timbral_synthesizer

__all__ = [
    "CompositionEngine",
    "composition_engine",
    "CompositionRequest",
    "CompositionResponse",
    "SymbolicComposition",
    "CompositionCycle",
    "SwaraEvent",
    "ValidationResult",
    "ValidationDiagnostic",
    "RagaConstraints",
    "TalaConstraints",
    "MelodyGenerator",
    "RhythmGenerator",
    "CompositionValidator",
    "AudioRenderer",
    "audio_renderer",
    "ShrutiMapper",
    "shruti_mapper",
    "ShrutiPitch",
    "IntonationProfile",
    "ExpressionController",
    "expression_controller",
    "TimbralSynthesizer",
    "timbral_synthesizer",
]
