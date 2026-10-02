"""
RagaDetector for RagaRhythm AI.

Identifies likely Hindustani raga candidates from melodic evidence produced by
TonicEstimator, PitchExtractor, and SwaraAnalyzer.

Combines multiple independent musical signals:
1. Swara presence / absence and varjit (forbidden) swara filtering
2. Pitch Class Distribution (PCD) cosine similarity against theoretical profiles
3. Vadi (king note) & Samvadi (minister note) prominence
4. Aroha (ascending) and Avaroha (descending) transition probability
5. Characteristic Melodic Phrase (Pakad / Chalan) sequence matching via MelodicMotifMatcher
6. Microtonal and register usage
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from backend.app.analysis.pitch_extractor import PitchExtractionResult
from backend.app.analysis.swara_analyzer import SwaraAnalysisResult, SwaraSegment
from backend.app.analysis.tonic_estimator import TonicEstimationResult
from backend.app.analysis.motif_matcher import (
    MelodicMotifMatcher,
    MelodicPhraseParser,
    MotifMatchEvidence,
    ALL_SWARA_SYMBOLS,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Verified Canonical Hindustani Raga Knowledge Representation (70 Ragas)
# ============================================================================

RAGA_KNOWLEDGE_BASE: Dict[str, Dict[str, Any]] = {
    "yaman": {
        "name": "Yaman",
        "aliases": ["yaman_kalyan", "kalyan"],
        "thaat": "Kalyan",
        "swaras": ["S", "R", "G", "M", "P", "D", "N"],
        "varjit": ["r", "g", "m", "d", "n"],
        "vadi": "G",
        "samvadi": "N",
        "aroha": ["N", "R", "G", "M", "D", "N", "S"],
        "avaroha": ["S", "N", "D", "P", "M", "G", "R", "S"],
        "pakad_motifs": [["N", "R", "G"], ["M", "D", "N", "S"], ["G", "M", "D", "P"], ["R", "G", "R", "S"], ["N", "D", "S"], ["M", "D", "N"]],
        "time": "Evening (First Prahar of Night)",
        "mood": "Shringara (Romantic, Peaceful)",
        "pcd_template": {"S": 0.12, "R": 0.16, "G": 0.22, "M": 0.16, "P": 0.14, "D": 0.10, "N": 0.10},
    },
    "bhairavi": {
        "name": "Bhairavi",
        "aliases": ["bhairabi"],
        "thaat": "Bhairavi",
        "swaras": ["S", "r", "g", "m", "P", "d", "n"],
        "varjit": ["R", "G", "M", "D", "N"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "r", "g", "m", "P", "d", "n", "S"],
        "avaroha": ["S", "n", "d", "P", "m", "g", "r", "S"],
        "pakad_motifs": [["m", "g", "S", "r", "S"], ["d", "P", "m", "P"], ["g", "m", "d", "P"], ["d", "r", "S"], ["g", "r", "S"]],
        "time": "Morning (All-time in modern recitals)",
        "mood": "Bhakti, Karuna (Devotional, Melancholic)",
        "pcd_template": {"S": 0.16, "r": 0.14, "g": 0.16, "m": 0.20, "P": 0.14, "d": 0.10, "n": 0.10},
    },
    "bhairav": {
        "name": "Bhairav",
        "aliases": ["raag_bhairav"],
        "thaat": "Bhairav",
        "swaras": ["S", "r", "G", "m", "P", "d", "N"],
        "varjit": ["R", "g", "M", "D", "n"],
        "vadi": "d",
        "samvadi": "r",
        "aroha": ["S", "r", "G", "m", "P", "d", "N", "S"],
        "avaroha": ["S", "N", "d", "P", "m", "G", "r", "S"],
        "pakad_motifs": [["G", "m", "d", "P"], ["G", "m", "r", "S"], ["d", "P", "G", "m"], ["S", "r", "G"], ["G", "r", "S"]],
        "time": "Early Morning (Dawn)",
        "mood": "Shanta, Gambhira (Solemn, Meditative)",
        "pcd_template": {"S": 0.16, "r": 0.20, "G": 0.14, "m": 0.18, "P": 0.10, "d": 0.16, "N": 0.06},
    },
    "todi": {
        "name": "Todi",
        "aliases": ["miyan_ki_todi", "miya_ki_todi"],
        "thaat": "Todi",
        "swaras": ["S", "r", "g", "M", "P", "d", "N"],
        "varjit": ["R", "G", "m", "D", "n"],
        "vadi": "d",
        "samvadi": "g",
        "aroha": ["S", "r", "g", "M", "d", "N", "S"],
        "avaroha": ["S", "N", "d", "P", "M", "g", "r", "S"],
        "pakad_motifs": [["r", "g", "r", "S"], ["M", "d", "N", "S"], ["d", "M", "g", "r", "S"], ["N", "S", "d"], ["N", "d", "P"]],
        "time": "Late Morning",
        "mood": "Karuna (Profound, Contemplative)",
        "pcd_template": {"S": 0.14, "r": 0.16, "g": 0.18, "M": 0.14, "P": 0.10, "d": 0.18, "N": 0.10},
    },
    "bhoopali": {
        "name": "Bhoopali",
        "aliases": ["bhupali", "bhoop"],
        "thaat": "Kalyan",
        "swaras": ["S", "R", "G", "P", "D"],
        "varjit": ["r", "g", "m", "M", "d", "n", "N"],
        "vadi": "G",
        "samvadi": "D",
        "aroha": ["S", "R", "G", "P", "D", "S"],
        "avaroha": ["S", "D", "P", "G", "R", "S"],
        "pakad_motifs": [["G", "R", "S", "D", "S"], ["P", "G", "D", "P", "G"], ["S", "R", "G", "P", "G"], ["S", "D", "S", "R"], ["D", "S", "R", "G"]],
        "time": "First Prahar of Night",
        "mood": "Shanta, Bhakti (Calm, Serene)",
        "pcd_template": {"S": 0.18, "R": 0.18, "G": 0.26, "P": 0.20, "D": 0.18},
    },
    "malkauns": {
        "name": "Malkauns",
        "aliases": ["malkosh"],
        "thaat": "Bhairavi",
        "swaras": ["S", "g", "m", "d", "n"],
        "varjit": ["r", "R", "G", "M", "P", "D", "N"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "g", "m", "d", "n", "S"],
        "avaroha": ["S", "n", "d", "m", "g", "S"],
        "pakad_motifs": [["g", "m", "d", "m", "g", "S"], ["m", "d", "n", "d", "m"], ["d", "n", "S", "g", "m"], ["d", "n", "S"], ["n", "d", "m"]],
        "time": "Midnight (Third Prahar of Night)",
        "mood": "Veer, Gambhira (Meditative, Introspective)",
        "pcd_template": {"S": 0.22, "g": 0.18, "m": 0.26, "d": 0.18, "n": 0.16},
    },
    "bageshri": {
        "name": "Bageshri",
        "aliases": ["bageshree"],
        "thaat": "Kafi",
        "swaras": ["S", "R", "g", "m", "P", "D", "n"],
        "varjit": ["r", "G", "M", "d", "N"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "g", "m", "D", "n", "S"],
        "avaroha": ["S", "n", "D", "m", "P", "D", "g", "m", "R", "S"],
        "pakad_motifs": [["D", "n", "S", "g", "m"], ["m", "P", "D", "g", "m"], ["g", "m", "R", "S"], ["n", "D", "m"]],
        "time": "Late Night",
        "mood": "Shringara (Deep Emotion, Longing)",
        "pcd_template": {"S": 0.18, "R": 0.10, "g": 0.16, "m": 0.24, "P": 0.08, "D": 0.14, "n": 0.10},
    },
    "desh": {
        "name": "Desh",
        "aliases": ["des"],
        "thaat": "Khamaj",
        "swaras": ["S", "R", "G", "m", "P", "D", "n", "N"],
        "varjit": ["r", "g", "M", "d"],
        "vadi": "R",
        "samvadi": "P",
        "aroha": ["S", "R", "m", "P", "N", "S"],
        "avaroha": ["S", "n", "D", "P", "m", "G", "R", "S"],
        "pakad_motifs": [["R", "m", "P", "N", "S"], ["R", "n", "D", "P"], ["m", "G", "R", "S"], ["P", "N", "S", "R"]],
        "time": "Second Prahar of Night",
        "mood": "Deshbhakti, Shringara (Joyful, Lyrical)",
        "pcd_template": {"S": 0.14, "R": 0.20, "G": 0.12, "m": 0.16, "P": 0.18, "D": 0.08, "n": 0.06, "N": 0.06},
    },
    "kafi": {
        "name": "Kafi",
        "aliases": ["raag_kafi"],
        "thaat": "Kafi",
        "swaras": ["S", "R", "g", "m", "P", "D", "n"],
        "varjit": ["r", "G", "M", "d", "N"],
        "vadi": "P",
        "samvadi": "S",
        "aroha": ["S", "R", "g", "m", "P", "D", "n", "S"],
        "avaroha": ["S", "n", "D", "P", "m", "g", "R", "S"],
        "pakad_motifs": [["S", "R", "g", "m", "P"], ["m", "P", "D", "n", "P"], ["P", "m", "g", "R", "S"], ["R", "g", "m", "P"]],
        "time": "Late Night / Spring",
        "mood": "Hori, Shringara (Expressive, Vibrant)",
        "pcd_template": {"S": 0.16, "R": 0.14, "g": 0.16, "m": 0.16, "P": 0.18, "D": 0.10, "n": 0.10},
    },
    "kedar": {
        "name": "Kedar",
        "aliases": ["raag_kedar"],
        "thaat": "Kalyan",
        "swaras": ["S", "R", "G", "m", "M", "P", "D", "N"],
        "varjit": ["r", "g", "d", "n"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "m", "M", "P", "D", "P", "S"],
        "avaroha": ["S", "N", "D", "P", "M", "P", "D", "P", "m", "S", "R", "S"],
        "pakad_motifs": [["S", "m"], ["m", "P", "D", "P", "m"], ["P", "m", "G", "R", "S"], ["D", "P", "m"], ["m", "S", "R", "S"]],
        "time": "Late Evening",
        "mood": "Shanta, Gambhira (Majestic, Regal)",
        "pcd_template": {"S": 0.18, "R": 0.10, "G": 0.08, "m": 0.22, "M": 0.10, "P": 0.18, "D": 0.08, "N": 0.06},
    },
    "hindol_pancham": {
        "name": "Hindol Pancham",
        "aliases": ["hindol"],
        "thaat": "Kalyan",
        "swaras": ["S", "G", "M", "P", "D", "N"],
        "varjit": ["r", "R", "g", "m", "d", "n"],
        "vadi": "D",
        "samvadi": "G",
        "aroha": ["S", "G", "M", "D", "N", "S"],
        "avaroha": ["S", "N", "D", "M", "G", "S"],
        "pakad_motifs": [["S", "G", "M", "D", "M", "G"], ["M", "D", "N", "D", "M"], ["G", "M", "P", "D", "N", "S"]],
        "time": "Dawn / Morning",
        "mood": "Utsaha (Bright, Springtime)",
        "pcd_template": {"S": 0.18, "G": 0.24, "M": 0.22, "P": 0.10, "D": 0.16, "N": 0.10},
    },
    "jogiya": {
        "name": "Jogiya",
        "aliases": ["jogia"],
        "thaat": "Bhairav",
        "swaras": ["S", "r", "m", "P", "d"],
        "varjit": ["R", "g", "G", "M", "D", "n", "N"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "r", "m", "P", "d", "S"],
        "avaroha": ["S", "d", "P", "m", "P", "d", "m", "r", "S"],
        "pakad_motifs": [["S", "r", "m", "P"], ["m", "P", "d", "m", "r", "S"], ["r", "S"], ["d", "P", "m", "P"]],
        "time": "Early Morning (Dawn)",
        "mood": "Vairagya, Karuna (Ascetic, Renunciation)",
        "pcd_template": {"S": 0.24, "r": 0.18, "m": 0.24, "P": 0.16, "d": 0.18},
    },
    "komal_rishabh_asavari": {
        "name": "Komal Rishabh Asavari",
        "aliases": ["komal_rishav_aasavari"],
        "thaat": "Asavari",
        "swaras": ["S", "r", "g", "m", "P", "d", "n"],
        "varjit": ["R", "G", "M", "D", "N"],
        "vadi": "d",
        "samvadi": "g",
        "aroha": ["S", "r", "m", "P", "d", "S"],
        "avaroha": ["S", "n", "d", "P", "m", "g", "r", "S"],
        "pakad_motifs": [["m", "P", "d", "P"], ["m", "P", "n", "d", "P"], ["g", "r", "S"], ["r", "m", "P", "d"]],
        "time": "Late Morning",
        "mood": "Karuna, Gambhira (Tender, Pensive)",
        "pcd_template": {"S": 0.16, "r": 0.14, "g": 0.16, "m": 0.16, "P": 0.16, "d": 0.16, "n": 0.06},
    },
    "lalit": {
        "name": "Lalit",
        "aliases": ["lalat", "lalita_gauri"],
        "thaat": "Purvi",
        "swaras": ["S", "r", "G", "m", "M", "d", "N"],
        "varjit": ["R", "g", "P", "D", "n"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "r", "G", "m", "M", "d", "N", "S"],
        "avaroha": ["S", "N", "d", "M", "m", "G", "r", "S"],
        "pakad_motifs": [["m", "M", "m", "G"], ["r", "S", "N", "r", "S"], ["G", "M", "d", "S"], ["d", "S"], ["r", "N", "d", "M"]],
        "time": "Brahma Muhurta (Pre-dawn)",
        "mood": "Gambhira (Mystical, Deep)",
        "pcd_template": {"S": 0.16, "r": 0.14, "G": 0.16, "m": 0.18, "M": 0.14, "d": 0.14, "N": 0.08},
    },
    "jait_kalyan": {
        "name": "Jait Kalyan",
        "aliases": ["jait"],
        "thaat": "Kalyan",
        "swaras": ["S", "R", "G", "P", "D"],
        "varjit": ["r", "g", "m", "M", "d", "n", "N"],
        "vadi": "P",
        "samvadi": "S",
        "aroha": ["S", "R", "G", "P", "D", "S"],
        "avaroha": ["S", "D", "P", "G", "R", "S"],
        "pakad_motifs": [["P", "G", "R", "S"], ["S", "D", "P", "G", "P"], ["S", "R", "G", "P", "D", "S"]],
        "time": "First Prahar of Night",
        "mood": "Gambhira, Shanta (Stately, Peaceful)",
        "pcd_template": {"S": 0.18, "R": 0.16, "G": 0.20, "P": 0.26, "D": 0.20},
    },
    "shree": {
        "name": "Shree",
        "aliases": ["sree", "sri"],
        "thaat": "Purvi",
        "swaras": ["S", "r", "G", "M", "P", "d", "N"],
        "varjit": ["R", "g", "m", "D", "n"],
        "vadi": "r",
        "samvadi": "P",
        "aroha": ["S", "r", "M", "P", "N", "S"],
        "avaroha": ["S", "N", "d", "P", "M", "G", "r", "S"],
        "pakad_motifs": [["r", "N", "d", "P"], ["P", "N", "S", "r"], ["N", "r", "S"], ["G", "r", "S"], ["r", "P"]],
        "time": "Dusk / Sunset (Sandhiprakash)",
        "mood": "Gambhira, Shanta (Majestic, Meditative)",
        "pcd_template": {"S": 0.16, "r": 0.20, "G": 0.12, "M": 0.14, "P": 0.18, "d": 0.12, "N": 0.08},
    },
    "bihag": {
        "name": "Bihag",
        "aliases": ["raag_bihag"],
        "thaat": "Bilawal",
        "swaras": ["S", "R", "G", "m", "M", "P", "D", "N"],
        "varjit": ["r", "g", "d", "n"],
        "vadi": "G",
        "samvadi": "N",
        "aroha": ["N", "S", "G", "m", "P", "N", "S"],
        "avaroha": ["S", "N", "D", "P", "M", "G", "m", "G", "R", "S"],
        "pakad_motifs": [["P", "N", "S", "G"], ["G", "m", "G"], ["P", "M", "G", "m", "G"], ["M", "G", "R", "S"], ["P", "N", "S"]],
        "time": "Second Prahar of Night",
        "mood": "Shringara (Romantic, Soothing)",
        "pcd_template": {"S": 0.14, "R": 0.08, "G": 0.22, "m": 0.14, "M": 0.08, "P": 0.18, "D": 0.06, "N": 0.10},
    },
    "marwa": {
        "name": "Marwa",
        "aliases": ["raag_marwa"],
        "thaat": "Marwa",
        "swaras": ["S", "r", "G", "M", "D", "N"],
        "varjit": ["R", "g", "m", "P", "d", "n"],
        "vadi": "D",
        "samvadi": "G",
        "aroha": ["N", "r", "G", "M", "D", "N", "S"],
        "avaroha": ["S", "N", "D", "M", "G", "r", "S"],
        "pakad_motifs": [["D", "N", "r", "G"], ["r", "G", "r", "S"], ["D", "M", "G", "r"], ["r", "N", "D", "S"], ["G", "r"]],
        "time": "Sunset (Sandhiprakash)",
        "mood": "Vairagya, Veer (Mystical, Haunting)",
        "pcd_template": {"S": 0.12, "r": 0.18, "G": 0.22, "M": 0.16, "D": 0.20, "N": 0.12},
    },
    "bhimpalasi": {
        "name": "Bhimpalasi",
        "aliases": ["bhimpalas"],
        "thaat": "Kafi",
        "swaras": ["S", "R", "g", "m", "P", "D", "n"],
        "varjit": ["r", "G", "M", "d", "N"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["n", "S", "g", "m", "P", "n", "S"],
        "avaroha": ["S", "n", "D", "P", "m", "g", "R", "S"],
        "pakad_motifs": [["n", "S", "g", "m"], ["m", "P", "g", "m"], ["P", "m", "g", "R", "S"], ["n", "D", "P"], ["P", "S", "n"]],
        "time": "Late Afternoon (Third Prahar of Day)",
        "mood": "Shringara, Karuna (Poignant, Yearning)",
        "pcd_template": {"S": 0.16, "R": 0.10, "g": 0.16, "m": 0.22, "P": 0.16, "D": 0.08, "n": 0.12},
    },
    "bairagi": {
        "name": "Bairagi",
        "aliases": ["bairagi_bhairav"],
        "thaat": "Bhairav",
        "swaras": ["S", "r", "m", "P", "n"],
        "varjit": ["R", "g", "G", "M", "d", "D", "N"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "r", "m", "P", "n", "S"],
        "avaroha": ["S", "n", "P", "m", "r", "S"],
        "pakad_motifs": [["P", "m", "r"], ["P", "n", "S"], ["r", "m", "P"], ["n", "P", "m", "r", "S"]],
        "time": "Early Morning (Dawn)",
        "mood": "Vairagya, Shanta (Detached, Meditative)",
        "pcd_template": {"S": 0.22, "r": 0.18, "m": 0.22, "P": 0.20, "n": 0.18},
    },
    "ahir_bhairav": {
        "name": "Ahir Bhairav",
        "aliases": ["aahir_bhairon", "ahir_bhairon"],
        "thaat": "Bhairav",
        "swaras": ["S", "r", "G", "m", "P", "D", "n"],
        "varjit": ["R", "g", "M", "d", "N"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "r", "G", "m", "P", "D", "n", "S"],
        "avaroha": ["S", "n", "D", "P", "m", "G", "r", "S"],
        "pakad_motifs": [["D", "n", "r", "S"], ["G", "m", "P", "D", "n"], ["m", "G", "r", "S"], ["S", "m"], ["G", "r"]],
        "time": "Early Morning (Dawn)",
        "mood": "Bhakti, Shanta (Devotional, Serene)",
        "pcd_template": {"S": 0.16, "r": 0.16, "G": 0.14, "m": 0.20, "P": 0.14, "D": 0.10, "n": 0.10},
    },
    "bhatiyar": {
        "name": "Bhatiyar",
        "aliases": ["raag_bhatiyar"],
        "thaat": "Marwa",
        "swaras": ["S", "r", "G", "m", "M", "P", "D", "N"],
        "varjit": ["R", "g", "d", "n"],
        "vadi": "M",
        "samvadi": "S",
        "aroha": ["S", "r", "S", "D", "P", "M", "D", "N", "S"],
        "avaroha": ["S", "N", "D", "P", "M", "G", "r", "S"],
        "pakad_motifs": [["D", "N", "r", "S"], ["D", "N", "r", "G", "r", "N", "D"], ["G", "r", "S"], ["D", "N", "r", "m"], ["D", "N", "G"]],
        "time": "Pre-Dawn / Early Morning",
        "mood": "Veer, Gambhira (Bold, Resolute)",
        "pcd_template": {"S": 0.16, "r": 0.14, "G": 0.14, "m": 0.08, "M": 0.16, "P": 0.12, "D": 0.12, "N": 0.08},
    },
    "gaud_malhar": {
        "name": "Gaud Malhar",
        "aliases": ["gaudmalhar"],
        "thaat": "Kafi",
        "swaras": ["S", "R", "G", "m", "P", "D", "n", "N"],
        "varjit": ["r", "g", "M", "d"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "R", "G", "m", "P", "N", "D", "N", "S"],
        "avaroha": ["S", "D", "n", "P", "m", "G", "R", "S"],
        "pakad_motifs": [["N", "S", "R", "G", "m"], ["m", "R", "P"], ["D", "n", "P", "G", "P", "m"], ["m", "G", "R", "G", "R", "S"]],
        "time": "Monsoon / Any time",
        "mood": "Shringara (Joyful, Playful)",
        "pcd_template": {"S": 0.16, "R": 0.14, "G": 0.12, "m": 0.20, "P": 0.16, "D": 0.10, "n": 0.06, "N": 0.06},
    },
    "multani": {
        "name": "Multani",
        "aliases": ["raag_multani"],
        "thaat": "Todi",
        "swaras": ["S", "r", "g", "M", "P", "d", "N"],
        "varjit": ["R", "G", "m", "D", "n"],
        "vadi": "P",
        "samvadi": "S",
        "aroha": ["N", "S", "g", "M", "P", "N", "S"],
        "avaroha": ["S", "N", "d", "P", "M", "g", "r", "S"],
        "pakad_motifs": [["N", "S", "g", "M", "P"], ["M", "g", "r", "S"], ["g", "M", "P", "N"], ["P", "M", "g"], ["g", "r", "S"]],
        "time": "Late Afternoon (Fourth Prahar of Day)",
        "mood": "Karuna, Shanta (Yearning, Somber)",
        "pcd_template": {"S": 0.14, "r": 0.12, "g": 0.16, "M": 0.18, "P": 0.20, "d": 0.10, "N": 0.10},
    },
    "shuddha_kalyan": {
        "name": "Shuddha Kalyan",
        "aliases": ["sudh_kalyan"],
        "thaat": "Kalyan",
        "swaras": ["S", "R", "G", "M", "P", "D", "N"],
        "varjit": ["r", "g", "m", "d", "n"],
        "vadi": "G",
        "samvadi": "D",
        "aroha": ["S", "R", "G", "P", "D", "S"],
        "avaroha": ["S", "N", "D", "P", "M", "G", "R", "S"],
        "pakad_motifs": [["G", "R", "S", "D", "S"], ["P", "G", "R", "S"], ["S", "R", "S", "P"], ["S", "N", "D"], ["P", "G"]],
        "time": "First Prahar of Night",
        "mood": "Shanta, Gambhira (Grand, Serene)",
        "pcd_template": {"S": 0.18, "R": 0.16, "G": 0.22, "M": 0.06, "P": 0.18, "D": 0.14, "N": 0.06},
    },
    "megh": {
        "name": "Megh",
        "aliases": ["megh_malhar"],
        "thaat": "Kafi",
        "swaras": ["S", "R", "m", "P", "n"],
        "varjit": ["r", "g", "G", "M", "d", "D", "N"],
        "vadi": "S",
        "samvadi": "P",
        "aroha": ["S", "R", "m", "P", "n", "S"],
        "avaroha": ["S", "n", "P", "m", "R", "S"],
        "pakad_motifs": [["n", "S", "R", "m", "R"], ["m", "P", "n", "P"], ["R", "m", "P", "n", "S"], ["R", "m", "R", "S"], ["P", "n", "R"]],
        "time": "Monsoon / Late Night",
        "mood": "Veer, Shringara (Grand, Rain)",
        "pcd_template": {"S": 0.22, "R": 0.18, "m": 0.20, "P": 0.22, "n": 0.18},
    },
    "gawti": {
        "name": "Gawti",
        "aliases": ["gavti"],
        "thaat": "Khamaj",
        "swaras": ["S", "R", "G", "m", "P", "D", "n"],
        "varjit": ["r", "g", "M", "d", "N"],
        "vadi": "G",
        "samvadi": "n",
        "aroha": ["S", "G", "m", "P", "D", "n", "S"],
        "avaroha": ["S", "n", "D", "P", "m", "G", "R", "S"],
        "pakad_motifs": [["n", "S", "G"], ["G", "m", "R", "n"], ["G", "m", "R", "S"], ["P", "D", "n", "S"]],
        "time": "Second Prahar of Night",
        "mood": "Shringara (Sweet, Expressive)",
        "pcd_template": {"S": 0.16, "R": 0.12, "G": 0.20, "m": 0.16, "P": 0.16, "D": 0.10, "n": 0.10},
    },
    "bilaskhani_todi": {
        "name": "Bilaskhani Todi",
        "aliases": ["bilaskhani"],
        "thaat": "Bhairavi",
        "swaras": ["S", "r", "g", "m", "P", "d", "n"],
        "varjit": ["R", "G", "M", "D", "N"],
        "vadi": "d",
        "samvadi": "g",
        "aroha": ["S", "r", "g", "P", "d", "S"],
        "avaroha": ["S", "n", "d", "P", "m", "g", "r", "S"],
        "pakad_motifs": [["r", "g", "P", "d", "P"], ["g", "r", "n", "d"], ["d", "S"], ["r", "g", "P"], ["g", "r", "S"]],
        "time": "Late Morning (Second Prahar of Day)",
        "mood": "Karuna (Mournful, Deep)",
        "pcd_template": {"S": 0.16, "r": 0.16, "g": 0.18, "m": 0.12, "P": 0.14, "d": 0.16, "n": 0.08},
    },
    "hameer": {
        "name": "Hameer",
        "aliases": ["hamir"],
        "thaat": "Kalyan",
        "swaras": ["S", "R", "G", "m", "M", "P", "D", "N"],
        "varjit": ["r", "g", "d", "n"],
        "vadi": "D",
        "samvadi": "G",
        "aroha": ["S", "R", "G", "M", "P", "D", "N", "S"],
        "avaroha": ["S", "N", "D", "P", "M", "P", "D", "P", "m", "G", "R", "S"],
        "pakad_motifs": [["G", "m", "R"], ["G", "m", "N", "D"], ["N", "D", "P"], ["G", "m", "P"], ["D", "N", "S"]],
        "time": "First Prahar of Night",
        "mood": "Veer, Gambhira (Stately, Majestic)",
        "pcd_template": {"S": 0.14, "R": 0.12, "G": 0.16, "m": 0.12, "M": 0.10, "P": 0.16, "D": 0.14, "N": 0.06},
    },
    "shuddh_sarang": {
        "name": "Shuddh Sarang",
        "aliases": ["shuddha_sarang", "sudh_sarang"],
        "thaat": "Kafi",
        "swaras": ["S", "R", "m", "M", "P", "D", "N"],
        "varjit": ["r", "g", "G", "d", "n"],
        "vadi": "R",
        "samvadi": "P",
        "aroha": ["S", "R", "m", "M", "P", "N", "S"],
        "avaroha": ["S", "N", "D", "P", "M", "P", "m", "R", "S"],
        "pakad_motifs": [["N", "D", "P"], ["P", "N", "D", "S", "N", "R"], ["N", "S", "R", "m", "R"], ["m", "R", "N", "S", "N"], ["N", "R", "S"]],
        "time": "Early Afternoon",
        "mood": "Shanta (Calm, Bright)",
        "pcd_template": {"S": 0.16, "R": 0.20, "m": 0.16, "M": 0.12, "P": 0.18, "D": 0.08, "N": 0.10},
    },
    "maru_bihag": {
        "name": "Maru Bihag",
        "aliases": ["marubihag"],
        "thaat": "Kalyan",
        "swaras": ["S", "R", "G", "m", "M", "P", "D", "N"],
        "varjit": ["r", "g", "d", "n"],
        "vadi": "G",
        "samvadi": "N",
        "aroha": ["S", "G", "m", "P", "N", "S"],
        "avaroha": ["S", "N", "D", "P", "M", "G", "m", "G", "R", "S"],
        "pakad_motifs": [["P", "N"], ["M", "G", "R", "S"], ["N", "S", "R", "S", "N"], ["S", "m", "G", "M", "S"], ["S", "G", "M", "P", "M", "P"]],
        "time": "Second Prahar of Night",
        "mood": "Shringara (Romantic, Graceful)",
        "pcd_template": {"S": 0.14, "R": 0.10, "G": 0.20, "m": 0.14, "M": 0.12, "P": 0.16, "D": 0.06, "N": 0.08},
    },
    "dhani": {
        "name": "Dhani",
        "aliases": ["raag_dhani"],
        "thaat": "Kafi",
        "swaras": ["S", "g", "m", "P", "n"],
        "varjit": ["r", "R", "G", "M", "d", "D", "N"],
        "vadi": "g",
        "samvadi": "n",
        "aroha": ["S", "g", "m", "P", "n", "S"],
        "avaroha": ["S", "n", "P", "m", "g", "S"],
        "pakad_motifs": [["P", "m", "g"], ["g", "m", "P", "n"], ["n", "P", "m", "g"], ["S", "g", "m", "P"]],
        "time": "Any time (Often Afternoon)",
        "mood": "Shringara, Shanta (Lyrical, Cheerful)",
        "pcd_template": {"S": 0.20, "g": 0.22, "m": 0.18, "P": 0.20, "n": 0.20},
    },
    "puriya": {
        "name": "Puriya",
        "aliases": ["raag_puriya"],
        "thaat": "Marwa",
        "swaras": ["S", "r", "G", "M", "D", "N"],
        "varjit": ["R", "g", "m", "P", "d", "n"],
        "vadi": "G",
        "samvadi": "N",
        "aroha": ["N", "r", "G", "M", "D", "N", "S"],
        "avaroha": ["S", "N", "D", "M", "G", "r", "S"],
        "pakad_motifs": [["r", "N"], ["r", "S"], ["M", "D", "N"], ["G", "M", "D", "M", "G"], ["r", "S"]],
        "time": "Dusk / Sunset",
        "mood": "Gambhira (Solemn, Serene)",
        "pcd_template": {"S": 0.10, "r": 0.16, "G": 0.24, "M": 0.18, "D": 0.18, "N": 0.14},
    },
    "jog": {
        "name": "Jog",
        "aliases": ["raag_jog"],
        "thaat": "Kafi",
        "swaras": ["S", "g", "G", "m", "P", "n"],
        "varjit": ["r", "R", "M", "d", "D", "N"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "G", "m", "P", "n", "S"],
        "avaroha": ["S", "n", "P", "m", "G", "m", "g", "S"],
        "pakad_motifs": [["g", "n", "S"], ["g", "S", "n"], ["G", "m", "P", "n"], ["P", "n", "S"], ["n", "S", "G"], ["m", "g", "S"]],
        "time": "Late Night (Second Prahar of Night)",
        "mood": "Gambhira, Karuna (Haunting, Evocative)",
        "pcd_template": {"S": 0.18, "g": 0.12, "G": 0.16, "m": 0.22, "P": 0.18, "n": 0.14},
    },
    "abhogi": {
        "name": "Abhogi",
        "aliases": ["abhogi_kanada"],
        "thaat": "Kafi",
        "swaras": ["S", "R", "g", "m", "D"],
        "varjit": ["r", "G", "M", "P", "d", "n", "N"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "R", "g", "m", "D", "S"],
        "avaroha": ["S", "D", "m", "g", "R", "S"],
        "pakad_motifs": [["D", "S"], ["D", "S", "R", "g", "R"], ["g", "R", "m"], ["m", "g", "R"], ["g", "R", "S", "D"]],
        "time": "Late Night",
        "mood": "Shringara (Melodious, Enchanting)",
        "pcd_template": {"S": 0.22, "R": 0.18, "g": 0.20, "m": 0.22, "D": 0.18},
    },
    "bibhas": {
        "name": "Bibhas",
        "aliases": ["vibhas"],
        "thaat": "Bhairav",
        "swaras": ["S", "r", "G", "P", "d"],
        "varjit": ["R", "g", "m", "M", "D", "n", "N"],
        "vadi": "d",
        "samvadi": "G",
        "aroha": ["S", "r", "G", "P", "d", "S"],
        "avaroha": ["S", "d", "P", "G", "r", "S"],
        "pakad_motifs": [["D", "S", "r", "S"], ["r", "G"], ["P", "G", "r", "S"], ["d", "P", "G", "r", "S"], ["D", "S", "r", "G"]],
        "time": "Early Morning (Dawn)",
        "mood": "Bhakti, Veer (Majestic, Morning Light)",
        "pcd_template": {"S": 0.20, "r": 0.20, "G": 0.22, "P": 0.18, "d": 0.20},
    },
    "nat_bhairav": {
        "name": "Nat Bhairav",
        "aliases": ["nat_bhairon"],
        "thaat": "Bhairav",
        "swaras": ["S", "R", "G", "m", "P", "d", "N"],
        "varjit": ["r", "g", "M", "D", "n"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "R", "G", "m", "P", "d", "N", "S"],
        "avaroha": ["S", "N", "d", "P", "m", "G", "R", "S"],
        "pakad_motifs": [["N", "S", "d"], ["N", "d"], ["d", "N", "S"], ["S", "R", "G", "m", "P", "m"], ["G", "m", "R"]],
        "time": "Early Morning",
        "mood": "Bhakti, Gambhira (Solemn, Pure)",
        "pcd_template": {"S": 0.16, "R": 0.16, "G": 0.14, "m": 0.20, "P": 0.14, "d": 0.12, "N": 0.08},
    },
    "rageshree": {
        "name": "Rageshree",
        "aliases": ["rageshri", "raageshree"],
        "thaat": "Khamaj",
        "swaras": ["S", "R", "G", "m", "D", "n"],
        "varjit": ["r", "g", "M", "P", "d", "N"],
        "vadi": "G",
        "samvadi": "n",
        "aroha": ["S", "R", "G", "m", "D", "n", "S"],
        "avaroha": ["S", "n", "D", "m", "G", "R", "S"],
        "pakad_motifs": [["n", "S", "D"], ["m", "D", "n"], ["n", "S"], ["D", "n", "S", "G"], ["G", "m", "R"]],
        "time": "Late Night (Second Prahar of Night)",
        "mood": "Shringara (Sensuous, Peaceful)",
        "pcd_template": {"S": 0.18, "R": 0.14, "G": 0.22, "m": 0.18, "D": 0.16, "n": 0.12},
    },
    "bahar": {
        "name": "Bahar",
        "aliases": ["raag_bahar"],
        "thaat": "Kafi",
        "swaras": ["S", "R", "g", "m", "P", "D", "n", "N"],
        "varjit": ["r", "G", "M", "d"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "m", "P", "g", "m", "n", "D", "N", "S"],
        "avaroha": ["S", "n", "D", "P", "m", "g", "m", "R", "S"],
        "pakad_motifs": [["S", "m"], ["m", "P", "g", "m"], ["g", "m", "S", "R"], ["m", "S"], ["R", "n", "S", "m"], ["m", "P", "n", "D", "N", "S"]],
        "time": "Spring / Midnight",
        "mood": "Utsaha, Shringara (Springtime, Joy)",
        "pcd_template": {"S": 0.16, "R": 0.10, "g": 0.14, "m": 0.24, "P": 0.12, "D": 0.08, "n": 0.08, "N": 0.08},
    },
    "khamaj": {
        "name": "Khamaj",
        "aliases": ["maajh_khamaj", "majh_khamaj"],
        "thaat": "Khamaj",
        "swaras": ["S", "R", "G", "m", "P", "D", "n", "N"],
        "varjit": ["r", "g", "M", "d"],
        "vadi": "G",
        "samvadi": "N",
        "aroha": ["S", "G", "m", "P", "D", "N", "S"],
        "avaroha": ["S", "n", "D", "P", "m", "G", "R", "S"],
        "pakad_motifs": [["R", "G", "m"], ["m", "D"], ["n", "D", "P"], ["m", "G"], ["G", "m", "P", "D", "n", "D", "P"]],
        "time": "Late Night",
        "mood": "Shringara (Romantic, Playful)",
        "pcd_template": {"S": 0.14, "R": 0.10, "G": 0.20, "m": 0.16, "P": 0.16, "D": 0.10, "n": 0.08, "N": 0.06},
    },
    "kalavati": {
        "name": "Kalavati",
        "aliases": ["kalawati"],
        "thaat": "Khamaj",
        "swaras": ["S", "G", "P", "D", "n"],
        "varjit": ["r", "R", "g", "m", "M", "d", "N"],
        "vadi": "P",
        "samvadi": "S",
        "aroha": ["S", "G", "P", "D", "n", "S"],
        "avaroha": ["S", "n", "D", "P", "G", "S"],
        "pakad_motifs": [["n", "S", "G"], ["D", "P", "G", "S"], ["n", "S"], ["D", "P", "G"]],
        "time": "Midnight",
        "mood": "Shringara, Shanta (Pleasing, Ecstatic)",
        "pcd_template": {"S": 0.20, "G": 0.22, "P": 0.24, "D": 0.20, "n": 0.14},
    },
    "saraswati": {
        "name": "Saraswati",
        "aliases": ["raag_saraswati"],
        "thaat": "Kalyan",
        "swaras": ["S", "R", "m", "M", "P", "D", "n"],
        "varjit": ["r", "g", "G", "d", "N"],
        "vadi": "R",
        "samvadi": "P",
        "aroha": ["S", "R", "m", "P", "D", "S"],
        "avaroha": ["S", "n", "D", "P", "M", "R", "S"],
        "pakad_motifs": [["P", "M", "R"], ["M", "R", "n"], ["D", "S"], ["R", "M", "P"], ["R", "n", "S"]],
        "time": "First Prahar of Night",
        "mood": "Bhakti, Shanta (Divine, Intellect)",
        "pcd_template": {"S": 0.18, "R": 0.20, "m": 0.10, "M": 0.14, "P": 0.18, "D": 0.10, "n": 0.10},
    },
    "chandrakauns": {
        "name": "Chandrakauns",
        "aliases": ["raag_chandrakauns"],
        "thaat": "Bhairavi",
        "swaras": ["S", "g", "m", "d", "N"],
        "varjit": ["r", "R", "G", "M", "P", "D", "n"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "g", "m", "d", "N", "S"],
        "avaroha": ["S", "N", "d", "m", "g", "S"],
        "pakad_motifs": [["d", "N", "S"], ["m", "d", "N", "d", "m"], ["g", "m", "d", "N", "S"], ["N", "d", "m", "g", "S"]],
        "time": "Midnight",
        "mood": "Gambhira (Introspective, Night)",
        "pcd_template": {"S": 0.22, "g": 0.18, "m": 0.26, "d": 0.18, "N": 0.16},
    },
    "suha": {
        "name": "Suha",
        "aliases": ["sooha_kanada", "sooha", "suha_kanada"],
        "thaat": "Kafi",
        "swaras": ["S", "R", "g", "m", "P", "n"],
        "varjit": ["r", "G", "M", "d", "D", "N"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "g", "m", "P", "n", "S"],
        "avaroha": ["S", "n", "P", "m", "P", "g", "m", "R", "S"],
        "pakad_motifs": [["n", "P"], ["m", "P", "g", "m"], ["R", "S"], ["n", "S", "g", "m", "P"]],
        "time": "Mid-Day / Afternoon",
        "mood": "Gambhira, Veer (Majestic, Courageous)",
        "pcd_template": {"S": 0.18, "R": 0.12, "g": 0.18, "m": 0.22, "P": 0.18, "n": 0.12},
    },
    "sohani": {
        "name": "Sohani",
        "aliases": ["sohini"],
        "thaat": "Marwa",
        "swaras": ["S", "r", "G", "M", "D", "N"],
        "varjit": ["R", "g", "m", "P", "d", "n"],
        "vadi": "G",
        "samvadi": "N",
        "aroha": ["S", "G", "M", "D", "N", "S"],
        "avaroha": ["S", "N", "D", "M", "G", "r", "S"],
        "pakad_motifs": [["S", "G", "M", "D", "N", "S"], ["N", "D", "M", "G"], ["G", "M", "D", "N"], ["S", "r", "S", "N", "D"]],
        "time": "Pre-Dawn (Last Prahar of Night)",
        "mood": "Shringara (Delicate, Romantic)",
        "pcd_template": {"S": 0.10, "r": 0.12, "G": 0.24, "M": 0.18, "D": 0.20, "N": 0.16},
    },
    "triveni_gauri": {
        "name": "Triveni Gauri",
        "aliases": ["triveni"],
        "thaat": "Purvi",
        "swaras": ["S", "r", "G", "P", "d", "N"],
        "varjit": ["R", "g", "m", "M", "D", "n"],
        "vadi": "G",
        "samvadi": "N",
        "aroha": ["S", "r", "G", "P", "d", "N", "S"],
        "avaroha": ["S", "N", "d", "P", "G", "r", "S"],
        "pakad_motifs": [["G", "P", "d", "N", "S"], ["d", "P", "G", "r"], ["r", "G", "P", "d", "P"]],
        "time": "Dusk / Sunset",
        "mood": "Gambhira (Mystical)",
        "pcd_template": {"S": 0.18, "r": 0.16, "G": 0.22, "P": 0.18, "d": 0.16, "N": 0.10},
    },
    "lalit_pancham": {
        "name": "Lalit Pancham",
        "aliases": ["lalitpancham"],
        "thaat": "Purvi",
        "swaras": ["S", "r", "G", "m", "M", "P", "d", "N"],
        "varjit": ["R", "g", "D", "n"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "r", "G", "m", "M", "d", "N", "S"],
        "avaroha": ["S", "N", "d", "P", "M", "m", "G", "r", "S"],
        "pakad_motifs": [["m", "M", "m", "G"], ["d", "M", "P", "M", "m"], ["G", "r", "S"]],
        "time": "Pre-Dawn",
        "mood": "Gambhira (Contemplative)",
        "pcd_template": {"S": 0.14, "r": 0.14, "G": 0.16, "m": 0.18, "M": 0.12, "P": 0.10, "d": 0.10, "N": 0.06},
    },
    "madhukauns": {
        "name": "Madhukauns",
        "aliases": ["madhu_kauns"],
        "thaat": "Kafi",
        "swaras": ["S", "g", "M", "P", "n"],
        "varjit": ["r", "R", "G", "m", "d", "D", "N"],
        "vadi": "P",
        "samvadi": "S",
        "aroha": ["S", "g", "M", "P", "n", "S"],
        "avaroha": ["S", "n", "P", "M", "g", "S"],
        "pakad_motifs": [["g", "M", "P", "n"], ["P", "M", "g", "S"], ["S", "g", "M", "P"]],
        "time": "Late Night",
        "mood": "Shanta, Gambhira (Serene)",
        "pcd_template": {"S": 0.22, "g": 0.20, "M": 0.18, "P": 0.22, "n": 0.18},
    },
    "nat_kamod": {
        "name": "Nat Kamod",
        "aliases": ["natkamod"],
        "thaat": "Kalyan",
        "swaras": ["S", "R", "G", "m", "M", "P", "D", "N"],
        "varjit": ["r", "g", "d", "n"],
        "vadi": "R",
        "samvadi": "P",
        "aroha": ["S", "R", "G", "m", "P", "D", "N", "S"],
        "avaroha": ["S", "N", "D", "P", "M", "P", "G", "m", "R", "S"],
        "pakad_motifs": [["R", "G", "m", "P"], ["M", "P", "D", "P"], ["G", "m", "R", "S"], ["R", "P"]],
        "time": "First Prahar of Night",
        "mood": "Shringara (Romantic)",
        "pcd_template": {"S": 0.14, "R": 0.18, "G": 0.14, "m": 0.14, "M": 0.08, "P": 0.18, "D": 0.08, "N": 0.06},
    },
    "mishra_piloo": {
        "name": "Mishra Piloo",
        "aliases": ["pilu", "piloo", "mishra_pilu"],
        "thaat": "Kafi",
        "swaras": ["S", "R", "g", "G", "m", "P", "d", "D", "n", "N"],
        "varjit": ["r", "M"],
        "vadi": "g",
        "samvadi": "n",
        "aroha": ["N", "S", "g", "m", "P", "N", "S"],
        "avaroha": ["S", "n", "D", "P", "m", "g", "R", "S"],
        "pakad_motifs": [["n", "D", "P"], ["P", "d", "P"], ["g", "m", "P"], ["g", "R", "S"], ["N", "S", "g"]],
        "time": "Third Prahar of Day (Afternoon / Evening)",
        "mood": "Shringara, Karuna (Light Classical, Thumri)",
        "pcd_template": {"S": 0.14, "R": 0.12, "g": 0.14, "G": 0.08, "m": 0.14, "P": 0.16, "d": 0.06, "D": 0.06, "n": 0.06, "N": 0.04},
    },
    "mishra_kalingada": {
        "name": "Mishra Kalingada",
        "aliases": ["kalingada", "kalingda"],
        "thaat": "Bhairav",
        "swaras": ["S", "r", "G", "m", "P", "d", "N"],
        "varjit": ["R", "g", "M", "D", "n"],
        "vadi": "P",
        "samvadi": "S",
        "aroha": ["S", "r", "G", "m", "P", "d", "N", "S"],
        "avaroha": ["S", "N", "d", "P", "m", "G", "r", "S"],
        "pakad_motifs": [["S", "r", "G", "m", "P"], ["d", "P", "m", "G"], ["r", "G", "r", "S"]],
        "time": "Last Prahar of Night (Pre-Dawn)",
        "mood": "Bhakti, Shringara (Devotional, Semi-classical)",
        "pcd_template": {"S": 0.16, "r": 0.16, "G": 0.16, "m": 0.14, "P": 0.20, "d": 0.12, "N": 0.06},
    },
    "poorva": {
        "name": "Poorva",
        "aliases": ["purvi", "poorvi"],
        "thaat": "Purvi",
        "swaras": ["S", "r", "G", "M", "P", "d", "N"],
        "varjit": ["R", "g", "m", "D", "n"],
        "vadi": "G",
        "samvadi": "N",
        "aroha": ["S", "r", "G", "M", "P", "d", "N", "S"],
        "avaroha": ["S", "N", "d", "P", "M", "G", "r", "S"],
        "pakad_motifs": [["S", "r", "G"], ["M", "d", "N", "S"], ["N", "d", "P", "M", "G"], ["r", "G", "r", "S"]],
        "time": "Sunset / Twilight",
        "mood": "Gambhira (Mystical)",
        "pcd_template": {"S": 0.14, "r": 0.16, "G": 0.22, "M": 0.16, "P": 0.14, "d": 0.10, "N": 0.08},
    },
    "lagan_gandhar": {
        "name": "Lagan Gandhar",
        "aliases": ["lagangandhar"],
        "thaat": "Kafi",
        "swaras": ["S", "R", "g", "m", "P", "D", "n"],
        "varjit": ["r", "G", "M", "d", "N"],
        "vadi": "g",
        "samvadi": "D",
        "aroha": ["S", "R", "g", "m", "D", "n", "S"],
        "avaroha": ["S", "n", "D", "P", "m", "g", "R", "S"],
        "pakad_motifs": [["g", "m", "D", "n"], ["m", "g", "R", "S"], ["S", "R", "g", "m"]],
        "time": "Late Night",
        "mood": "Shringara",
        "pcd_template": {"S": 0.16, "R": 0.14, "g": 0.20, "m": 0.16, "P": 0.10, "D": 0.14, "n": 0.10},
    },
    "khokar": {
        "name": "Khokar",
        "aliases": ["raag_khokar"],
        "thaat": "Kafi",
        "swaras": ["S", "R", "g", "m", "P", "D", "n"],
        "varjit": ["r", "G", "M", "d", "N"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "R", "g", "m", "P", "D", "n", "S"],
        "avaroha": ["S", "n", "D", "P", "m", "g", "R", "S"],
        "pakad_motifs": [["m", "P", "D", "n", "P"], ["m", "g", "R", "S"], ["S", "R", "g", "m"]],
        "time": "Late Night",
        "mood": "Gambhira",
        "pcd_template": {"S": 0.16, "R": 0.12, "g": 0.16, "m": 0.22, "P": 0.16, "D": 0.10, "n": 0.08},
    },
    "dagori_deepki": {
        "name": "Dagori Deepki",
        "aliases": ["dagori", "deepki"],
        "thaat": "Kalyan",
        "swaras": ["S", "R", "G", "M", "P", "D", "N"],
        "varjit": ["r", "g", "m", "d", "n"],
        "vadi": "G",
        "samvadi": "D",
        "aroha": ["S", "R", "G", "M", "P", "D", "N", "S"],
        "avaroha": ["S", "N", "D", "P", "M", "G", "R", "S"],
        "pakad_motifs": [["G", "M", "D", "P"], ["G", "R", "S"], ["S", "R", "G", "M"]],
        "time": "First Prahar of Night",
        "mood": "Gambhira",
        "pcd_template": {"S": 0.14, "R": 0.16, "G": 0.22, "M": 0.16, "P": 0.14, "D": 0.10, "N": 0.08},
    },
    "khat": {
        "name": "Khat",
        "aliases": ["khat_todi"],
        "thaat": "Asavari",
        "swaras": ["S", "r", "R", "g", "m", "P", "d", "n"],
        "varjit": ["G", "M", "D", "N"],
        "vadi": "d",
        "samvadi": "g",
        "aroha": ["S", "r", "g", "m", "P", "d", "n", "S"],
        "avaroha": ["S", "n", "d", "P", "m", "g", "R", "r", "S"],
        "pakad_motifs": [["r", "g", "m", "P", "d"], ["m", "g", "R", "r", "S"], ["d", "P", "m", "g"]],
        "time": "Morning (Second Prahar of Day)",
        "mood": "Karuna",
        "pcd_template": {"S": 0.14, "r": 0.12, "R": 0.06, "g": 0.18, "m": 0.16, "P": 0.16, "d": 0.12, "n": 0.06},
    },
    "mian_malhar": {
        "name": "Mian Malhar",
        "aliases": ["miya_malhar", "miyan_malhar"],
        "thaat": "Kafi",
        "swaras": ["S", "R", "g", "m", "P", "D", "n", "N"],
        "varjit": ["r", "G", "M", "d"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "R", "g", "m", "R", "P", "m", "P", "n", "D", "N", "S"],
        "avaroha": ["S", "D", "n", "P", "m", "g", "m", "R", "S"],
        "pakad_motifs": [["R", "g", "m", "R", "S"], ["m", "P", "n", "D", "N", "S"], ["D", "n", "P"], ["m", "g", "m", "R", "S"]],
        "time": "Monsoon / Midnight",
        "mood": "Gambhira, Shringara (Grand, Majestic Rain)",
        "pcd_template": {"S": 0.16, "R": 0.14, "g": 0.12, "m": 0.22, "P": 0.16, "D": 0.06, "n": 0.08, "N": 0.06},
    },
    "ramdasi_malhar": {
        "name": "Ramdasi Malhar",
        "aliases": ["ramdasi"],
        "thaat": "Kafi",
        "swaras": ["S", "R", "g", "G", "m", "P", "D", "n", "N"],
        "varjit": ["r", "M", "d"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "R", "G", "m", "P", "n", "D", "N", "S"],
        "avaroha": ["S", "n", "D", "P", "m", "g", "m", "R", "S"],
        "pakad_motifs": [["R", "G", "m", "P"], ["m", "g", "m", "R", "S"], ["n", "D", "N", "S"], ["m", "P", "n", "D", "P"]],
        "time": "Monsoon / Midnight",
        "mood": "Shringara (Lyrical Rain)",
        "pcd_template": {"S": 0.16, "R": 0.12, "g": 0.08, "G": 0.10, "m": 0.20, "P": 0.16, "D": 0.08, "n": 0.06, "N": 0.04},
    },
    "sawani": {
        "name": "Sawani",
        "aliases": ["raag_sawani"],
        "thaat": "Kalyan",
        "swaras": ["S", "R", "G", "m", "M", "P", "D", "N"],
        "varjit": ["r", "g", "d", "n"],
        "vadi": "P",
        "samvadi": "S",
        "aroha": ["S", "R", "G", "m", "P", "D", "N", "S"],
        "avaroha": ["S", "N", "D", "P", "M", "P", "m", "G", "R", "S"],
        "pakad_motifs": [["P", "M", "P", "m", "G"], ["R", "G", "m", "P"], ["D", "N", "S"], ["P", "m", "G", "R", "S"]],
        "time": "Monsoon / Afternoon",
        "mood": "Shringara",
        "pcd_template": {"S": 0.14, "R": 0.12, "G": 0.16, "m": 0.14, "M": 0.08, "P": 0.20, "D": 0.10, "N": 0.06},
    },
    "gauri": {
        "name": "Gauri",
        "aliases": ["ramgauri_gauri"],
        "thaat": "Bhairav",
        "swaras": ["S", "r", "G", "m", "P", "d", "N"],
        "varjit": ["R", "g", "M", "D", "n"],
        "vadi": "r",
        "samvadi": "P",
        "aroha": ["S", "r", "G", "m", "P", "d", "N", "S"],
        "avaroha": ["S", "N", "d", "P", "m", "G", "r", "S"],
        "pakad_motifs": [["r", "G", "m", "P"], ["d", "P", "m", "G"], ["r", "G", "r", "S"], ["r", "S", "N", "r", "S"]],
        "time": "Dusk / Sunset",
        "mood": "Gambhira, Bhakti",
        "pcd_template": {"S": 0.16, "r": 0.16, "G": 0.18, "m": 0.12, "P": 0.20, "d": 0.12, "N": 0.06},
    },
    "kirwani": {
        "name": "Kirwani",
        "aliases": ["keeravani"],
        "thaat": "Kirwani",
        "swaras": ["S", "R", "g", "m", "P", "d", "N"],
        "varjit": ["r", "G", "M", "D", "n"],
        "vadi": "P",
        "samvadi": "S",
        "aroha": ["S", "R", "g", "m", "P", "d", "N", "S"],
        "avaroha": ["S", "N", "d", "P", "m", "g", "R", "S"],
        "pakad_motifs": [["R", "g", "m", "P"], ["d", "N", "S"], ["N", "d", "P"], ["m", "g", "R", "S"]],
        "time": "Midnight",
        "mood": "Karuna, Shringara (Expressive, Melodic)",
        "pcd_template": {"S": 0.16, "R": 0.14, "g": 0.16, "m": 0.14, "P": 0.18, "d": 0.12, "N": 0.10},
    },
    "puriya_dhanashree": {
        "name": "Puriya Dhanashree",
        "aliases": ["pooriya_dhanashree"],
        "thaat": "Purvi",
        "swaras": ["S", "r", "G", "M", "P", "d", "N"],
        "varjit": ["R", "g", "m", "D", "n"],
        "vadi": "P",
        "samvadi": "r",
        "aroha": ["N", "r", "G", "M", "P", "d", "N", "S"],
        "avaroha": ["S", "N", "d", "P", "M", "G", "r", "S"],
        "pakad_motifs": [["N", "r", "G"], ["M", "P", "d", "P"], ["M", "G", "r", "S"], ["r", "G", "r", "S"]],
        "time": "Dusk / Sunset (Sandhiprakash)",
        "mood": "Karuna, Shanta (Deep Devotion, Peaceful)",
        "pcd_template": {"S": 0.12, "r": 0.16, "G": 0.18, "M": 0.16, "P": 0.20, "d": 0.10, "N": 0.08},
    },
    "paraj": {
        "name": "Paraj",
        "aliases": ["raag_paraj"],
        "thaat": "Purvi",
        "swaras": ["S", "r", "G", "M", "P", "d", "N"],
        "varjit": ["R", "g", "m", "D", "n"],
        "vadi": "S",
        "samvadi": "P",
        "aroha": ["S", "G", "M", "P", "d", "N", "S"],
        "avaroha": ["S", "N", "d", "P", "M", "G", "r", "S"],
        "pakad_motifs": [["d", "N", "S"], ["P", "d", "P", "M", "G"], ["M", "d", "N", "S"], ["G", "M", "P", "M", "G"]],
        "time": "Last Prahar of Night (Pre-Dawn)",
        "mood": "Gambhira (Mysterious, Intense)",
        "pcd_template": {"S": 0.16, "r": 0.14, "G": 0.18, "M": 0.16, "P": 0.18, "d": 0.10, "N": 0.08},
    },
    "basanti_kedar": {
        "name": "Basanti Kedar",
        "aliases": ["basanti"],
        "thaat": "Kalyan",
        "swaras": ["S", "R", "G", "m", "M", "P", "D", "N"],
        "varjit": ["r", "g", "d", "n"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "m", "M", "P", "D", "N", "S"],
        "avaroha": ["S", "N", "D", "P", "M", "P", "D", "P", "m", "G", "R", "S"],
        "pakad_motifs": [["S", "m"], ["m", "P", "D", "P", "m"], ["P", "M", "G", "M", "d", "S"]],
        "time": "Spring / Night",
        "mood": "Shringara (Joyful, Spring)",
        "pcd_template": {"S": 0.16, "R": 0.10, "G": 0.12, "m": 0.20, "M": 0.10, "P": 0.16, "D": 0.10, "N": 0.06},
    },
    "asavari": {
        "name": "Asavari",
        "aliases": ["shuddha_asavari"],
        "thaat": "Asavari",
        "swaras": ["S", "R", "g", "m", "P", "d", "n"],
        "varjit": ["r", "G", "M", "D", "N"],
        "vadi": "d",
        "samvadi": "g",
        "aroha": ["S", "R", "m", "P", "d", "S"],
        "avaroha": ["S", "n", "d", "P", "m", "g", "R", "S"],
        "pakad_motifs": [["m", "P", "d", "P"], ["m", "P", "n", "d", "P"], ["g", "R", "S"], ["R", "m", "P", "d"]],
        "time": "Late Morning",
        "mood": "Karuna (Tender)",
        "pcd_template": {"S": 0.18, "R": 0.14, "g": 0.12, "m": 0.18, "P": 0.18, "d": 0.14, "n": 0.06},
    },
    "jaunpuri": {
        "name": "Jaunpuri",
        "aliases": ["jonpuri"],
        "thaat": "Asavari",
        "swaras": ["S", "R", "g", "m", "P", "d", "n"],
        "varjit": ["r", "G", "M", "D", "N"],
        "vadi": "d",
        "samvadi": "g",
        "aroha": ["S", "R", "m", "P", "d", "n", "S"],
        "avaroha": ["S", "n", "d", "P", "m", "g", "R", "S"],
        "pakad_motifs": [["m", "P", "n", "d", "P"], ["D", "m", "P", "g"], ["R", "m", "P"]],
        "time": "Late Morning",
        "mood": "Bhakti, Karuna (Devotional)",
        "pcd_template": {"S": 0.16, "R": 0.14, "g": 0.16, "m": 0.16, "P": 0.16, "d": 0.14, "n": 0.08},
    },
    "shankara": {
        "name": "Shankara",
        "aliases": ["shankar"],
        "thaat": "Bilawal",
        "swaras": ["S", "R", "G", "P", "D", "N"],
        "varjit": ["r", "g", "m", "M", "d", "n"],
        "vadi": "G",
        "samvadi": "N",
        "aroha": ["S", "G", "P", "N", "D", "S"],
        "avaroha": ["S", "N", "D", "P", "G", "P", "G", "R", "S"],
        "pakad_motifs": [["G", "P", "G", "R", "S"], ["N", "P", "G", "P"], ["S", "N", "D", "S"]],
        "time": "Late Night (Third Prahar of Night)",
        "mood": "Veer, Raudra (Bold, Heroic)",
        "pcd_template": {"S": 0.16, "R": 0.10, "G": 0.26, "P": 0.22, "D": 0.12, "N": 0.14},
    },
    "tilak_kamod": {
        "name": "Tilak Kamod",
        "aliases": ["tilakkamod"],
        "thaat": "Khamaj",
        "swaras": ["S", "R", "G", "m", "P", "D", "N"],
        "varjit": ["r", "g", "M", "d", "n"],
        "vadi": "S",
        "samvadi": "P",
        "aroha": ["S", "R", "G", "S", "R", "m", "P", "N", "S"],
        "avaroha": ["S", "P", "D", "m", "G", "S", "R", "G", "S", "N"],
        "pakad_motifs": [["S", "R", "G", "S", "R", "m", "P"], ["D", "m", "G", "S", "R"]],
        "time": "Second Prahar of Night",
        "mood": "Shringara (Light, Playful)",
        "pcd_template": {"S": 0.18, "R": 0.18, "G": 0.16, "m": 0.14, "P": 0.18, "D": 0.08, "N": 0.08},
    },
    "durga": {
        "name": "Durga",
        "aliases": ["raag_durga"],
        "thaat": "Bilawal",
        "swaras": ["S", "R", "m", "P", "D"],
        "varjit": ["r", "g", "G", "M", "d", "n", "N"],
        "vadi": "m",
        "samvadi": "S",
        "aroha": ["S", "R", "m", "P", "D", "S"],
        "avaroha": ["S", "D", "P", "m", "R", "S"],
        "pakad_motifs": [["m", "P", "D", "m"], ["R", "m", "P"], ["D", "P", "m", "R", "S"]],
        "time": "Second Prahar of Night",
        "mood": "Shanta, Gambhira (Pure, Noble)",
        "pcd_template": {"S": 0.22, "R": 0.18, "m": 0.22, "P": 0.20, "D": 0.18},
    },
    "jaijaiwanti": {
        "name": "Jaijaiwanti",
        "aliases": ["jayjaywanti"],
        "thaat": "Khamaj",
        "swaras": ["S", "R", "g", "G", "m", "P", "D", "n", "N"],
        "varjit": ["r", "M", "d"],
        "vadi": "R",
        "samvadi": "P",
        "aroha": ["S", "R", "G", "m", "P", "N", "S"],
        "avaroha": ["S", "n", "D", "P", "D", "m", "G", "R", "g", "R", "S"],
        "pakad_motifs": [["R", "g", "R", "S"], ["D", "n", "R"], ["R", "G", "m", "P"]],
        "time": "First Prahar of Night",
        "mood": "Shringara, Karuna (Poignant, Royal)",
        "pcd_template": {"S": 0.16, "R": 0.20, "g": 0.08, "G": 0.12, "m": 0.14, "P": 0.16, "D": 0.08, "n": 0.04, "N": 0.02},
    },
}


# ============================================================================
# Output Data Models
# ============================================================================

class RagaCandidate(BaseModel):
    """Structured hypothesis for a specific raga with decomposed evidence."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    raga_name: str = Field(..., description="Canonical raga name")
    raga_id: str = Field(..., description="Canonical snake_case raga identifier")
    thaat: str = Field(..., description="Parent Thaat scale family")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score [0.0, 1.0]")
    score: float = Field(..., description="Composite match score [0.0, 1.0]")
    feature_scores: Dict[str, float] = Field(default_factory=dict, description="Decomposable feature score contributions")
    matched_features: List[str] = Field(default_factory=list, description="Positively verified melodic features")
    missing_features: List[str] = Field(default_factory=list, description="Expected raga features absent in performance")
    contradictory_features: List[str] = Field(default_factory=list, description="Contradictory evidence (e.g. forbidden notes)")
    motif_evidence: Optional[MotifMatchEvidence] = Field(default=None, description="Detailed melodic motif match evidence")
    time: str = Field(default="Unknown", description="Traditional performance time")
    mood: str = Field(default="Unknown", description="Traditional aesthetic mood (Rasa)")


class RagaAnalysisResult(BaseModel):
    """Complete structured result of raga detection engine."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    detected_raga: str = Field(..., description="Top detected raga name, or 'INSUFFICIENT_EVIDENCE'")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence of primary prediction")
    top_candidates: List[RagaCandidate] = Field(default_factory=list, description="Ranked candidate hypotheses")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Detailed diagnostic metrics and feature tallies")
    swara_profile: Dict[str, float] = Field(default_factory=dict, description="Observed 12-tone Pitch Class Distribution")
    aroha_evidence: List[str] = Field(default_factory=list, description="Observed ascending transitions")
    avaroha_evidence: List[str] = Field(default_factory=list, description="Observed descending transitions")
    phrase_evidence: List[str] = Field(default_factory=list, description="Detected Pakad catch-phrases")
    tonic: Dict[str, Any] = Field(default_factory=dict, description="Estimated Sa tonic metadata")
    limitations: List[str] = Field(default_factory=list, description="Known analytical constraints")
    method: str = Field(default="multi_feature_pcd_pakad", description="Detection algorithm")

    def to_summary_dict(self) -> Dict[str, Any]:
        """Returns JSON-serializable summary metadata."""
        return {
            "detected_raga": self.detected_raga,
            "confidence": round(self.confidence, 3),
            "top_candidates": [
                {
                    "raga_name": c.raga_name,
                    "confidence": round(c.confidence, 3),
                    "score": round(c.score, 3),
                    "thaat": c.thaat,
                    "matched": c.matched_features[:3],
                    "contradictory": c.contradictory_features[:3],
                }
                for c in self.top_candidates[:3]
            ],
            "dominant_swaras": [k for k, v in sorted(self.swara_profile.items(), key=lambda x: x[1], reverse=True)[:4] if v > 0.05],
            "limitations": self.limitations,
            "method": self.method,
        }


# Precomputed template vectors and metadata for fast O(1) scoring
_PRECOMPUTED_PCD_TEMPLATES: Dict[str, Tuple[np.ndarray, float]] = {}
_PRECOMPUTED_RAGA_SWARAS: Dict[str, Tuple[set[str], set[str], set[Tuple[str, str]]]] = {}

for _r_id, _r_meta in RAGA_KNOWLEDGE_BASE.items():
    _tpl = _r_meta.get("pcd_template", {})
    _vec = np.array([_tpl.get(sym, 0.0) for sym in ALL_SWARA_SYMBOLS], dtype=np.float64)
    _vec = np.nan_to_num(_vec, nan=0.0, posinf=0.0, neginf=0.0)
    _norm = float(np.linalg.norm(_vec))
    _PRECOMPUTED_PCD_TEMPLATES[_r_id] = (_vec, _norm)

    _swaras = set(_r_meta.get("swaras", []))
    _varjit = set(_r_meta.get("varjit", []))
    _aroha = _r_meta.get("aroha", [])
    _avaroha = _r_meta.get("avaroha", [])
    _trans = set()
    for _i in range(len(_aroha) - 1):
        _trans.add((_aroha[_i], _aroha[_i + 1]))
    for _i in range(len(_avaroha) - 1):
        _trans.add((_avaroha[_i], _avaroha[_i + 1]))
    _PRECOMPUTED_RAGA_SWARAS[_r_id] = (_swaras, _varjit, _trans)


# ============================================================================
# RagaDetector Engine Implementation
# ============================================================================

class RagaDetector:
    """
    Interpretable, Multi-Feature Indian Classical Music Raga Detection Engine.
    
    Combines:
    1. Swara Presence / Varjit (Forbidden Swara) Consistency (25%)
    2. Pitch Class Distribution (PCD) Cosine Similarity (25%)
    3. Vadi & Samvadi Prominence Verification (15%)
    4. Aroha / Avaroha Transition Graph Matching (15%)
    5. Characteristic Melodic Phrase (Pakad) Sequence Matching via MelodicMotifMatcher (20%)
    """

    MIN_VOICED_COVERAGE_THRESHOLD = 15.0  # Require at least 15% voiced coverage
    AMBIGUITY_MARGIN = 0.04

    def __init__(
        self,
        knowledge_base: Optional[Dict[str, Dict[str, Any]]] = None,
        weight_swara: float = 0.25,
        weight_pcd: float = 0.25,
        weight_vadi: float = 0.15,
        weight_scale: float = 0.15,
        weight_phrase: float = 0.20,
    ):
        self.knowledge_base = knowledge_base or RAGA_KNOWLEDGE_BASE
        self.weight_swara = weight_swara
        self.weight_pcd = weight_pcd
        self.weight_vadi = weight_vadi
        self.weight_scale = weight_scale
        self.weight_phrase = weight_phrase

    def detect(
        self,
        swara_result: Union[SwaraAnalysisResult, Dict[str, Any]],
        tonic_input: Optional[Union[TonicEstimationResult, float, Dict[str, Any]]] = None,
        pitch_result: Optional[Union[PitchExtractionResult, Dict[str, Any]]] = None,
    ) -> RagaAnalysisResult:
        """
        Executes multi-feature raga candidate scoring and classification.
        
        Args:
            swara_result: SwaraAnalysisResult payload from SwaraAnalyzer.
            tonic_input: Optional TonicEstimationResult or tonic Hz float.
            pitch_result: Optional PitchExtractionResult for contour cross-checking.
            
        Returns:
            RagaAnalysisResult containing ranked hypotheses, scores, and diagnostics.
        """
        # Parse swara result
        if isinstance(swara_result, SwaraAnalysisResult):
            pcd = dict(swara_result.pitch_class_distribution)
            segments = swara_result.segments
            transitions = swara_result.transitions
            dominant_swaras = [s for s, _ in swara_result.dominant_swaras]
            swara_coverage = swara_result.swara_coverage_percentage
            tonic_hz = swara_result.tonic_hz
        elif isinstance(swara_result, dict):
            pcd = dict(swara_result.get("pitch_class_distribution", {}))
            segments = swara_result.get("segments", [])
            transitions = swara_result.get("transitions", [])
            dominant_swaras = [s for s, _ in swara_result.get("dominant_swaras", [])]
            swara_coverage = float(swara_result.get("swara_coverage_percentage", 0.0))
            tonic_hz = float(swara_result.get("tonic_hz", 0.0))
        else:
            raise ValueError(f"Unsupported swara_result type: {type(swara_result)}")

        # Parse tonic
        if tonic_input is not None:
            if isinstance(tonic_input, TonicEstimationResult):
                tonic_hz = float(tonic_input.tonic_hz)
            elif isinstance(tonic_input, (int, float)):
                tonic_hz = float(tonic_input)
            elif isinstance(tonic_input, dict):
                tonic_hz = float(tonic_input.get("tonic_hz", tonic_hz))

        tonic_info = {"tonic_hz": round(tonic_hz, 2) if tonic_hz > 0 else 0.0}

        # Insufficient evidence check: silence or very few voiced frames
        if swara_coverage < self.MIN_VOICED_COVERAGE_THRESHOLD or len(pcd) == 0:
            return self._insufficient_evidence_result(pcd, tonic_info, "Insufficient voiced melodic frames or silent audio.")

        # Clean & sanitize PCD vector
        clean_pcd: Dict[str, float] = {}
        for sym in ALL_SWARA_SYMBOLS:
            v = pcd.get(sym, 0.0)
            try:
                val = float(v)
                clean_pcd[sym] = 0.0 if (np.isnan(val) or np.isinf(val) or val < 0.0) else val
            except (TypeError, ValueError):
                clean_pcd[sym] = 0.0
        pcd = clean_pcd

        if sum(pcd.values()) < 1e-6:
            return self._insufficient_evidence_result(pcd, tonic_info, "Insufficient voiced melodic frames or silent audio.")

        # Extract sequence of non-empty segment symbols
        segment_symbols = [s.symbol if isinstance(s, SwaraSegment) else s.get("symbol", "") for s in segments]
        segment_symbols = [s for s in segment_symbols if s and s != "NONE"]

        # Convert observed transitions to string pairs
        observed_transitions = set()
        for t in transitions:
            if isinstance(t, (tuple, list)) and len(t) >= 2:
                observed_transitions.add((str(t[0]), str(t[1])))

        # Active swaras in observed performance (prominence > 1.5%)
        active_swaras = {sym for sym, weight in pcd.items() if weight >= 0.015 and sym in ALL_SWARA_SYMBOLS}

        # Precompute observed PCD vector and norm once for all candidates
        vec_obs = np.array([pcd.get(sym, 0.0) for sym in ALL_SWARA_SYMBOLS], dtype=np.float64)
        vec_obs = np.nan_to_num(vec_obs, nan=0.0, posinf=0.0, neginf=0.0)
        norm_obs = float(np.linalg.norm(vec_obs))
        precalc_obs = (vec_obs, norm_obs)

        # Evaluate every candidate raga in Knowledge Base
        candidates: List[RagaCandidate] = []
        for raga_id, raga_meta in self.knowledge_base.items():
            candidate = self._score_candidate(
                raga_id=raga_id,
                raga_meta=raga_meta,
                pcd=pcd,
                active_swaras=active_swaras,
                dominant_swaras=dominant_swaras,
                segment_symbols=segment_symbols,
                observed_transitions=observed_transitions,
                precalc_obs=precalc_obs,
            )
            candidates.append(candidate)

        # Rank candidates by composite score descending
        candidates.sort(key=lambda c: c.score, reverse=True)

        if not candidates:
            return self._insufficient_evidence_result(pcd, tonic_info, "No matching raga candidates found.")

        top_cand = candidates[0]
        runner_up = candidates[1] if len(candidates) > 1 else None

        # Calibrate final detected raga decision
        limitations: List[str] = []
        if top_cand.score < 0.38:
            detected_raga = "INSUFFICIENT_EVIDENCE"
            confidence = round(float(top_cand.score), 3)
            limitations.append("Top candidate match score is below minimum confidence threshold.")
        elif runner_up and (top_cand.score - runner_up.score) < self.AMBIGUITY_MARGIN:
            detected_raga = top_cand.raga_name
            confidence = round(float(top_cand.confidence * 0.85), 3)
            limitations.append(f"Ambiguous classification: '{top_cand.raga_name}' closely contested by '{runner_up.raga_name}'.")
        else:
            detected_raga = top_cand.raga_name
            confidence = round(float(top_cand.confidence), 3)

        # Collect phrase and scale evidence
        matched_phrases = []
        for c in candidates[:5]:
            for feat in c.matched_features:
                if "Pakad motif" in feat and feat not in matched_phrases:
                    matched_phrases.append(feat)

        aroha_ev = [f"{s1}->{s2}" for s1, s2 in observed_transitions if self._is_ascending(s1, s2)][:8]
        avaroha_ev = [f"{s1}->{s2}" for s1, s2 in observed_transitions if not self._is_ascending(s1, s2)][:8]

        evidence = {
            "total_candidates_evaluated": len(candidates),
            "top_candidate_score": round(top_cand.score, 4),
            "runner_up_score": round(runner_up.score, 4) if runner_up else 0.0,
            "swara_coverage_percentage": swara_coverage,
            "active_swaras": sorted(list(active_swaras)),
        }

        return RagaAnalysisResult(
            detected_raga=detected_raga,
            confidence=confidence,
            top_candidates=candidates[:10],
            evidence=evidence,
            swara_profile=pcd,
            aroha_evidence=aroha_ev,
            avaroha_evidence=avaroha_ev,
            phrase_evidence=matched_phrases,
            tonic=tonic_info,
            limitations=limitations,
            method="multi_feature_pcd_pakad",
        )

    def _score_candidate(
        self,
        raga_id: str,
        raga_meta: Dict[str, Any],
        pcd: Dict[str, float],
        active_swaras: set[str],
        dominant_swaras: List[str],
        segment_symbols: List[str],
        observed_transitions: set[Tuple[str, str]],
        precalc_obs: Optional[Tuple[np.ndarray, float]] = None,
    ) -> RagaCandidate:
        """
        Decomposable scoring logic for an individual raga candidate.
        """
        if raga_id in _PRECOMPUTED_RAGA_SWARAS:
            raga_swaras, varjit_swaras, expected_transitions = _PRECOMPUTED_RAGA_SWARAS[raga_id]
        else:
            raga_swaras = set(raga_meta.get("swaras", []))
            varjit_swaras = set(raga_meta.get("varjit", []))
            raga_aroha = raga_meta.get("aroha", [])
            raga_avaroha = raga_meta.get("avaroha", [])
            expected_transitions = set()
            for i in range(len(raga_aroha) - 1):
                expected_transitions.add((raga_aroha[i], raga_aroha[i + 1]))
            for i in range(len(raga_avaroha) - 1):
                expected_transitions.add((raga_avaroha[i], raga_avaroha[i + 1]))

        vadi = raga_meta.get("vadi", "")
        samvadi = raga_meta.get("samvadi", "")
        pcd_template = raga_meta.get("pcd_template", {})
        pakad_motifs = raga_meta.get("pakad_motifs", [])
        thaat = raga_meta.get("thaat", "Unknown")
        raga_name = raga_meta.get("name", raga_id.capitalize())

        matched_features: List[str] = []
        missing_features: List[str] = []
        contradictory_features: List[str] = []

        # 1. Swara Presence & Varjit Consistency Score (0.0 to 1.0)
        present_in_raga = raga_swaras.intersection(active_swaras)
        missing_in_perf = raga_swaras - active_swaras

        swara_match_ratio = len(present_in_raga) / len(raga_swaras) if raga_swaras else 0.0

        # Check forbidden (varjit) swara intrusions
        varjit_penalty = 0.0
        for v in varjit_swaras:
            v_weight = pcd.get(v, 0.0)
            if v_weight > 0.035:
                varjit_penalty += min(0.35, v_weight * 2.5)
                contradictory_features.append(f"Forbidden swara '{v}' present ({v_weight*100:.1f}%)")

        score_swara = max(0.0, swara_match_ratio - varjit_penalty)
        if swara_match_ratio > 0.85 and varjit_penalty < 0.05:
            matched_features.append(f"Strong swara match ({len(present_in_raga)}/{len(raga_swaras)} swaras)")
        elif missing_in_perf:
            missing_features.append(f"Missing expected swaras: {sorted(list(missing_in_perf))}")

        # 2. PCD Cosine Similarity (0.0 to 1.0)
        score_pcd = self._cosine_similarity(pcd, pcd_template, raga_id=raga_id, precalc_obs=precalc_obs)
        if score_pcd > 0.75:
            matched_features.append(f"High PCD profile correlation ({score_pcd*100:.1f}%)")

        # 3. Vadi & Samvadi Prominence Score (0.0 to 1.0)
        score_vadi = 0.0
        top_3_dominant = dominant_swaras[:3]
        top_5_dominant = dominant_swaras[:5]
        if vadi:
            if vadi in top_3_dominant or pcd.get(vadi, 0.0) >= 0.14:
                score_vadi += 0.65
                matched_features.append(f"Primary Vadi note '{vadi}' is dominant")
            elif vadi in top_5_dominant or pcd.get(vadi, 0.0) >= 0.08:
                score_vadi += 0.35
            else:
                missing_features.append(f"Vadi note '{vadi}' has weak presence ({pcd.get(vadi, 0.0)*100:.1f}%)")

        if samvadi:
            if samvadi in top_3_dominant or pcd.get(samvadi, 0.0) >= 0.14:
                score_vadi += 0.35
                matched_features.append(f"Samvadi note '{samvadi}' is dominant")
            elif samvadi in top_5_dominant or pcd.get(samvadi, 0.0) >= 0.08:
                score_vadi += 0.20

        score_vadi = min(1.0, score_vadi)

        # 4. Aroha / Avaroha Scale Transitions Score (0.0 to 1.0)
        score_scale = 0.0
        if expected_transitions:
            matched_trans = expected_transitions.intersection(observed_transitions)
            score_scale = min(1.0, len(matched_trans) / max(1, len(expected_transitions) * 0.5))
            if len(matched_trans) >= 3:
                matched_features.append(f"Matches {len(matched_trans)} canonical scale transitions")

        # 5. Characteristic Melodic Phrase (Pakad) Matching via MelodicMotifMatcher (0.0 to 1.0)
        motif_evidence: MotifMatchEvidence = MelodicMotifMatcher.match_raga_motifs(
            candidate_pakad_motifs=pakad_motifs,
            observed_segments_or_symbols=segment_symbols,
        )
        score_phrase = motif_evidence.match_score

        for m_str in motif_evidence.matched_motifs:
            matched_features.append(f"Pakad motif '{m_str}' detected")

        # Composite Weighted Score
        raw_score = (
            self.weight_swara * score_swara +
            self.weight_pcd * score_pcd +
            self.weight_vadi * score_vadi +
            self.weight_scale * score_scale +
            self.weight_phrase * score_phrase
        )
        if np.isnan(raw_score) or np.isinf(raw_score):
            raw_score = 0.0

        confidence = float(np.clip(raw_score, 0.0, 1.0))
        if np.isnan(confidence) or np.isinf(confidence):
            confidence = 0.0

        feature_scores = {
            "swara_consistency": round(float(score_swara) if np.isfinite(score_swara) else 0.0, 3),
            "pcd_similarity": round(float(score_pcd) if np.isfinite(score_pcd) else 0.0, 3),
            "vadi_samvadi": round(float(score_vadi) if np.isfinite(score_vadi) else 0.0, 3),
            "scale_transitions": round(float(score_scale) if np.isfinite(score_scale) else 0.0, 3),
            "pakad_motifs": round(float(score_phrase) if np.isfinite(score_phrase) else 0.0, 3),
            "motif_evidence": round(float(score_phrase) if np.isfinite(score_phrase) else 0.0, 3),
        }

        return RagaCandidate(
            raga_name=raga_name,
            raga_id=raga_id,
            thaat=thaat,
            confidence=round(confidence, 3),
            score=round(raw_score, 3),
            feature_scores=feature_scores,
            matched_features=matched_features,
            missing_features=missing_features,
            contradictory_features=contradictory_features,
            motif_evidence=motif_evidence,
            time=raga_meta.get("time", "Unknown"),
            mood=raga_meta.get("mood", "Unknown"),
        )

    def _cosine_similarity(
        self,
        obs_pcd: Dict[str, float],
        template_pcd: Dict[str, float],
        raga_id: Optional[str] = None,
        precalc_obs: Optional[Tuple[np.ndarray, float]] = None,
    ) -> float:
        """Computes cosine similarity between 12-dimensional pitch vectors."""
        if not obs_pcd:
            return 0.0

        if precalc_obs is not None:
            vec_obs, norm_obs = precalc_obs
        else:
            vec_obs = np.array([obs_pcd.get(sym, 0.0) for sym in ALL_SWARA_SYMBOLS], dtype=np.float64)
            vec_obs = np.nan_to_num(vec_obs, nan=0.0, posinf=0.0, neginf=0.0)
            norm_obs = float(np.linalg.norm(vec_obs))

        if norm_obs < 1e-9:
            return 0.0

        if raga_id and raga_id in _PRECOMPUTED_PCD_TEMPLATES:
            vec_tpl, norm_tpl = _PRECOMPUTED_PCD_TEMPLATES[raga_id]
        else:
            if not template_pcd:
                return 0.0
            vec_tpl = np.array([template_pcd.get(sym, 0.0) for sym in ALL_SWARA_SYMBOLS], dtype=np.float64)
            vec_tpl = np.nan_to_num(vec_tpl, nan=0.0, posinf=0.0, neginf=0.0)
            norm_tpl = float(np.linalg.norm(vec_tpl))

        if norm_tpl < 1e-9:
            return 0.0

        dot = float(np.dot(vec_obs, vec_tpl))
        sim = dot / (norm_obs * norm_tpl)
        if np.isnan(sim) or np.isinf(sim):
            return 0.0
        return float(np.clip(sim, 0.0, 1.0))

    def _is_ascending(self, s1: str, s2: str) -> bool:
        """Determines if transition s1 -> s2 is ascending in pitch."""
        try:
            i1 = ALL_SWARA_SYMBOLS.index(s1)
            i2 = ALL_SWARA_SYMBOLS.index(s2)
            return i2 > i1
        except ValueError:
            return False

    def _insufficient_evidence_result(
        self,
        pcd: Dict[str, float],
        tonic_info: Dict[str, Any],
        reason: str,
    ) -> RagaAnalysisResult:
        """Creates fallback result when audio or melodic evidence is inadequate."""
        return RagaAnalysisResult(
            detected_raga="INSUFFICIENT_EVIDENCE",
            confidence=0.0,
            top_candidates=[],
            evidence={"status": "insufficient_evidence", "reason": reason},
            swara_profile=pcd,
            aroha_evidence=[],
            avaroha_evidence=[],
            phrase_evidence=[],
            tonic=tonic_info,
            limitations=[reason],
            method="multi_feature_pcd_pakad",
        )
