"""
Audio analysis endpoints executing the unified DSP pipeline.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from backend.app.analysis.pipeline import (
    AnalysisPipeline,
    UnifiedAnalysisResult,
)
from backend.app.analysis.preprocessor import (
    AudioPreprocessingError,
    AudioTooLongError,
    InvalidAudioError,
)
from backend.app.core.exceptions import (
    AudioDurationExceededError,
    AudioValidationError,
    NotImplementedAPIError,
)
from backend.app.core.security import save_upload_temporarily
from backend.app.schemas.analysis import (
    AnalysisResponse,
    AnalysisWarningSchema,
    AudioMetadataSchema,
    BeatGridSummarySchema,
    MotifEvidenceSchema,
    PitchSummarySchema,
    RagaAlternativeSchema,
    RagaResultSchema,
    RhythmSummarySchema,
    SwaraSummarySchema,
    TalaCandidateSchema,
    TalaResultSchema,
    TonicResultSchema,
)
from backend.app.schemas.common import NotImplementedResponse

router = APIRouter(tags=["Analysis"])

# Pipeline singleton
pipeline = AnalysisPipeline()


def _format_analysis_response(analysis_id: str, result: UnifiedAnalysisResult, filename: str) -> AnalysisResponse:
    """Transforms internal UnifiedAnalysisResult into external API AnalysisResponse schema."""
    # Audio metadata
    audio_meta = AudioMetadataSchema(
        filename=filename,
        duration_seconds=result.audio_metadata.duration_seconds,
        sample_rate=result.audio_metadata.sample_rate,
        channels=result.audio_metadata.channels_original,
        format=os.path.splitext(filename)[1].replace(".", "").lower() if filename else "audio",
        is_silent=result.audio_metadata.is_silent,
        rms=result.audio_metadata.rms,
        peak_amplitude=result.audio_metadata.peak_amplitude,
    )

    # Tonic
    tonic = TonicResultSchema(
        frequency_hz=result.tonic.frequency_hz,
        note_name=result.tonic.note_name or "Unknown",
        octave=result.tonic.octave,
        cents_deviation=result.tonic.cents_deviation,
        confidence=result.tonic.confidence,
        is_ambiguous=result.tonic.is_ambiguous,
        runner_up_hz=result.tonic.runner_up_hz,
    )

    # Pitch
    pitch = PitchSummarySchema(
        total_frames=result.pitch.total_frames,
        voiced_frames=result.pitch.voiced_frames,
        voiced_percentage=result.pitch.voiced_percentage,
        frame_rate=result.pitch.frame_rate,
        mean_f0_hz=result.pitch.mean_f0_hz,
        min_f0_hz=result.pitch.min_f0_hz,
        max_f0_hz=result.pitch.max_f0_hz,
        method=result.pitch.method,
        downsampled_timestamps=result.pitch.downsampled_timestamps,
        downsampled_frequencies=result.pitch.downsampled_frequencies,
    )

    # Swara
    swara = SwaraSummarySchema(
        pitch_class_distribution=result.swara.pitch_class_distribution,
        active_swaras=result.swara.active_swaras,
        total_segments=result.swara.total_segments,
        mean_cents_deviation=result.swara.mean_cents_deviation,
        dominant_swaras=result.swara.dominant_swaras,
        transitions_top=result.swara.transitions_top,
    )

    # Raga
    raga_alts = [
        RagaAlternativeSchema(
            id=alt.raga_id,
            name=alt.name,
            thaat=alt.thaat,
            confidence=alt.confidence,
            composite_score=alt.composite_score,
        )
        for alt in result.raga.alternatives
    ]

    raga_motifs = [
        MotifEvidenceSchema(
            motif=mm.motif,
            motif_str=mm.motif_str,
            match_type=mm.match_type,
            matched_subsequence=mm.matched_subsequence,
            similarity_score=mm.similarity_score,
            start_time_seconds=mm.start_time_seconds,
            end_time_seconds=mm.end_time_seconds,
        )
        for mm in result.raga.motif_matches
    ]

    raga = RagaResultSchema(
        id=result.raga.predicted_raga_id,
        name=result.raga.predicted_raga,
        thaat=result.raga.thaat,
        time=result.raga.time,
        mood=result.raga.mood,
        vadi=result.raga.vadi,
        samvadi=result.raga.samvadi,
        aroha=result.raga.aroha,
        avaroha=result.raga.avaroha,
        confidence=result.raga.confidence,
        is_ambiguous=result.raga.is_ambiguous,
        alternatives=raga_alts,
        motif_matches=raga_motifs,
    )

    # Rhythm
    rhythm = RhythmSummarySchema(
        estimated_bpm=result.rhythm.estimated_bpm,
        laya=result.rhythm.laya,
        tempo_confidence=result.rhythm.tempo_confidence,
        total_onsets=result.rhythm.total_onsets,
        frame_rate=result.rhythm.frame_rate,
    )

    # Beat Grid
    beat_grid = BeatGridSummarySchema(
        beat_count=result.beat_grid.beat_count,
        beat_period=result.beat_grid.beat_period,
        bpm=result.beat_grid.bpm,
        confidence=result.beat_grid.confidence,
        selected_hypothesis=result.beat_grid.selected_hypothesis,
        first_beat_time=result.beat_grid.first_beat_time,
        sam_timestamps=result.beat_grid.sam_timestamps,
        cycle_length=result.beat_grid.cycle_length,
    )

    # Tala
    tala_cands = [
        TalaCandidateSchema(
            id=cand.tala_id,
            name=cand.name,
            matras=cand.matras,
            confidence=cand.confidence,
            composite_score=cand.composite_score,
        )
        for cand in result.tala.candidates
    ]

    tala = TalaResultSchema(
        id=result.tala.predicted_tala_id,
        name=result.tala.predicted_tala,
        matras=result.tala.matras,
        beats=result.tala.matras,
        vibhag_structure=result.tala.vibhag_structure,
        theka=result.tala.theka,
        sam_position=result.tala.sam_position,
        khali_positions=result.tala.khali_positions,
        tali_positions=result.tala.tali_positions,
        confidence=result.tala.confidence,
        is_ambiguous=result.tala.is_ambiguous,
        candidates=tala_cands,
        tempo_hypothesis=result.tala.tempo_hypothesis,
    )

    # Warnings
    warnings = [
        AnalysisWarningSchema(
            stage=w.stage,
            code=w.code,
            message=w.message,
        )
        for w in result.warnings
    ]

    return AnalysisResponse(
        analysis_id=analysis_id,
        status="completed",
        audio_metadata=audio_meta,
        tonic=tonic,
        pitch=pitch,
        swara=swara,
        raga=raga,
        rhythm=rhythm,
        beat_grid=beat_grid,
        tala=tala,
        warnings=warnings,
        processing_time_ms=result.processing_time_ms,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Audio Recording",
    description="Uploads and analyzes an Indian classical music audio recording, producing tonic estimation, swara extraction, raga classification, and rhythmic tala structure.",
)
async def analyze_audio(
    file: UploadFile = File(..., description="Audio file in MP3, WAV, FLAC, OGG, or M4A format (max 25 MB)"),
) -> AnalysisResponse:
    """
    Executes full multi-stage audio analysis pipeline with secure streaming and temp storage cleanup.
    """
    analysis_id = str(uuid.uuid4())

    async with save_upload_temporarily(file) as (temp_path, original_filename, file_size):
        try:
            result = pipeline.process_file(temp_path)
            return _format_analysis_response(analysis_id, result, original_filename)
        except AudioTooLongError as e:
            raise AudioDurationExceededError(str(e))
        except (InvalidAudioError, AudioPreprocessingError) as e:
            raise AudioValidationError(str(e))


@router.get(
    "/analysis/{analysis_id}",
    response_model=NotImplementedResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Get Async Analysis Status (Planned)",
    description="Retrieves the asynchronous status and result for an analysis job ID. Persistent background storage is planned for a future milestone; please use synchronous POST /api/v1/analyze for immediate results.",
)
async def get_analysis_by_id(analysis_id: str) -> NotImplementedResponse:
    """
    Explicit 501 Not Implemented placeholder contract for persistent analysis polling.
    """
    raise NotImplementedAPIError(
        message="Persistent analysis job storage and asynchronous polling will be available in a future release. Use synchronous POST /api/v1/analyze.",
        endpoint=f"/api/v1/analysis/{analysis_id}",
    )
