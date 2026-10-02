"""
Composition generation endpoint executing deterministic, validated algorithmic composition.
Integrates bounded LRU caching for symbolic scores and synthesized audio streams.
"""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Body, HTTPException, Query, Response, status

from backend.app.analysis.raga_detector import RAGA_KNOWLEDGE_BASE
from backend.app.analysis.tala_knowledge_base import get_tala, normalize_tala_lookup_key
from backend.app.composition import (
    CompositionRequest,
    CompositionResponse,
    composition_engine,
)
from backend.app.composition.cache import (
    AUDIO_RENDERER_VERSION,
    audio_cache,
    composition_cache,
    compute_audio_cache_key,
    compute_composition_cache_key,
)
from backend.app.composition.tala_constraints import EXTENDED_COMPOSITION_TALAS

router = APIRouter(tags=["Generation"])


def _is_valid_raga(raga_id: str) -> bool:
    if not raga_id or not isinstance(raga_id, str):
        return False
    clean = raga_id.lower().strip().replace(" ", "_").replace("-", "_")
    if clean in RAGA_KNOWLEDGE_BASE:
        return True
    for k, v in RAGA_KNOWLEDGE_BASE.items():
        if k.lower() == clean or v.get("name", "").lower() == clean.replace("_", " "):
            return True
    return False


def _is_valid_tala(tala_id: str) -> bool:
    if not tala_id or not isinstance(tala_id, str):
        return False
    clean = normalize_tala_lookup_key(tala_id)
    if get_tala(clean) is not None:
        return True
    if clean in EXTENDED_COMPOSITION_TALAS:
        return True
    for tid, tdef in EXTENDED_COMPOSITION_TALAS.items():
        if tid == clean or clean in tdef.aliases:
            return True
    return False


@router.post(
    "/generate",
    response_model=CompositionResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Indian Classical Composition",
    description="Generates a deterministic, validated symbolic Indian classical musical piece based on specified Raga, Tala, tempo, and creativity parameters.",
)
async def generate_composition(
    request: CompositionRequest = Body(..., description="Configuration parameters for composition generation"),
) -> CompositionResponse:
    """
    Executes algorithmic composition engine and returns validated symbolic score with caching.
    """
    if not _is_valid_raga(request.raga_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown or unsupported Raga: '{request.raga_id}'. Please select a valid raga from the catalog.",
        )

    if not _is_valid_tala(request.tala_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown or unsupported Tala: '{request.tala_id}'. Please select a valid tala from the catalog.",
        )

    # 1. Check Composition Cache
    cache_key = compute_composition_cache_key(request)
    cached_resp = composition_cache.get(cache_key)
    if cached_resp is not None:
        return cached_resp

    # 2. Generate Symbolic Composition
    symbolic_comp = composition_engine.compose(request)

    metadata: Dict[str, Any] = {
        "raga": symbolic_comp.raga_name,
        "thaat": symbolic_comp.thaat,
        "tala": symbolic_comp.tala_name,
        "matras": symbolic_comp.matras,
        "tempo_bpm": symbolic_comp.tempo_bpm,
        "laya": symbolic_comp.laya,
        "duration_seconds": symbolic_comp.duration_seconds,
        "total_cycles": symbolic_comp.total_cycles,
        "event_count": len(symbolic_comp.events),
        "seed": symbolic_comp.seed,
        "tuning_mode": request.tuning_mode or "canonical",
        "timbre": request.timbre or "ensemble",
    }

    warnings = [
        d.message for d in symbolic_comp.validation.diagnostics if d.severity == "warning"
    ]

    audio_url = (
        f"/api/v1/generate/wav?raga_id={symbolic_comp.raga_id}&tala_id={symbolic_comp.tala_id}"
        f"&tempo_bpm={symbolic_comp.tempo_bpm}&duration_seconds={int(symbolic_comp.duration_seconds)}"
        f"&seed={symbolic_comp.seed}&tuning_mode={request.tuning_mode or 'canonical'}&timbre={request.timbre or 'ensemble'}"
    )

    response = CompositionResponse(
        composition_id=symbolic_comp.composition_id,
        title=symbolic_comp.title,
        metadata=metadata,
        symbolic_composition=symbolic_comp,
        validation_result=symbolic_comp.validation,
        warnings=warnings,
        audio_available=True,
        audio_duration_seconds=symbolic_comp.duration_seconds,
        audio_url=audio_url,
    )

    # 3. Store in cache only if valid
    if symbolic_comp.validation.valid:
        composition_cache.set(cache_key, response)

    return response


@router.post(
    "/generate/wav",
    status_code=status.HTTP_200_OK,
    summary="Export Composition as Downloadable WAV",
    description="Renders a validated Indian classical composition into a downloadable 16-bit PCM WAV audio file with microtonal and timbral support.",
    responses={
        200: {
            "content": {"audio/wav": {}},
            "description": "Binary WAV audio stream",
        }
    },
)
async def export_composition_wav_post(
    request: CompositionRequest = Body(..., description="Configuration parameters for composition audio generation"),
) -> Response:
    """
    Renders composition to PCM and returns raw downloadable WAV binary stream with audio caching.
    """
    if not _is_valid_raga(request.raga_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown or unsupported Raga: '{request.raga_id}'.",
        )

    if not _is_valid_tala(request.tala_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown or unsupported Tala: '{request.tala_id}'.",
        )

    from backend.app.composition.audio_renderer import audio_renderer

    # 1. Compose symbolic score
    symbolic_comp = composition_engine.compose(request)
    tuning_mode = request.tuning_mode or "canonical"
    timbre = request.timbre or "ensemble"

    # 2. Check Audio Cache
    audio_key = compute_audio_cache_key(
        composition_id=symbolic_comp.composition_id,
        raga_id=symbolic_comp.raga_id,
        tala_id=symbolic_comp.tala_id,
        seed=symbolic_comp.seed,
        tempo_bpm=symbolic_comp.tempo_bpm,
        duration_seconds=symbolic_comp.duration_seconds,
        tuning_mode=tuning_mode,
        timbre=timbre,
        renderer_version=AUDIO_RENDERER_VERSION,
    )

    cached_wav = audio_cache.get(audio_key)
    if cached_wav is not None:
        wav_bytes = cached_wav
    else:
        wav_bytes = audio_renderer.render_wav_bytes(
            symbolic_comp,
            tuning_mode=tuning_mode,
            timbre=timbre,
        )
        if len(wav_bytes) > 44:
            audio_cache.set(audio_key, wav_bytes)

    filename = f"composition_{symbolic_comp.raga_id}_{symbolic_comp.tala_id}_{symbolic_comp.seed}.wav"

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "audio/wav",
            "Content-Length": str(len(wav_bytes)),
        },
    )


@router.get(
    "/generate/wav",
    status_code=status.HTTP_200_OK,
    summary="Direct Stream / Download Composition WAV",
    description="Direct GET endpoint for browser audio playback and download of generated classical composition.",
    responses={
        200: {
            "content": {"audio/wav": {}},
            "description": "Binary WAV audio stream",
        }
    },
)
async def export_composition_wav_get(
    raga_id: str = Query(default="yaman", description="Canonical Raga ID"),
    tala_id: str = Query(default="teental", description="Canonical Tala ID"),
    tempo_bpm: int = Query(default=84, ge=40, le=240, description="Tempo in BPM"),
    duration_seconds: int = Query(default=60, ge=15, le=300, description="Duration in seconds"),
    seed: int = Query(default=42, description="Random seed"),
    tonic: str = Query(default="C", description="Tonic note name"),
    tuning_mode: str = Query(default="canonical", description="Tuning mode ('canonical' or 'raga_aware')"),
    timbre: str = Query(default="ensemble", description="Timbre ('ensemble', 'flute', 'bowed')"),
) -> Response:
    """
    Direct GET streaming endpoint for browser audio element and download.
    """
    if not _is_valid_raga(raga_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown or unsupported Raga: '{raga_id}'.",
        )

    if not _is_valid_tala(tala_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown or unsupported Tala: '{tala_id}'.",
        )

    from backend.app.composition.audio_renderer import audio_renderer

    req = CompositionRequest(
        raga_id=raga_id,
        tala_id=tala_id,
        tempo_bpm=tempo_bpm,
        duration_seconds=duration_seconds,
        seed=seed,
        tonic=tonic,
        tuning_mode=tuning_mode,
        timbre=timbre,
    )

    symbolic_comp = composition_engine.compose(req)

    # Audio Cache Lookup
    audio_key = compute_audio_cache_key(
        composition_id=symbolic_comp.composition_id,
        raga_id=symbolic_comp.raga_id,
        tala_id=symbolic_comp.tala_id,
        seed=symbolic_comp.seed,
        tempo_bpm=symbolic_comp.tempo_bpm,
        duration_seconds=symbolic_comp.duration_seconds,
        tuning_mode=tuning_mode,
        timbre=timbre,
        renderer_version=AUDIO_RENDERER_VERSION,
    )

    cached_wav = audio_cache.get(audio_key)
    if cached_wav is not None:
        wav_bytes = cached_wav
    else:
        wav_bytes = audio_renderer.render_wav_bytes(
            symbolic_comp,
            tuning_mode=tuning_mode,
            timbre=timbre,
        )
        if len(wav_bytes) > 44:
            audio_cache.set(audio_key, wav_bytes)

    filename = f"composition_{symbolic_comp.raga_id}_{symbolic_comp.tala_id}_{symbolic_comp.seed}.wav"

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "audio/wav",
            "Content-Length": str(len(wav_bytes)),
        },
    )


@router.get(
    "/generate/cache/stats",
    status_code=status.HTTP_200_OK,
    summary="Get Composition and Audio Cache Statistics",
    description="Returns current memory utilization, hits, misses, and entry counts for backend caches.",
)
async def get_cache_statistics() -> Dict[str, Any]:
    """Inspects runtime LRU cache metrics."""
    return {
        "composition_cache": composition_cache.stats(),
        "audio_cache": audio_cache.stats(),
        "renderer_version": AUDIO_RENDERER_VERSION,
    }


@router.post(
    "/generate/cache/clear",
    status_code=status.HTTP_200_OK,
    summary="Clear Composition and Audio Caches",
    description="Flushes all cached compositions and synthesized WAV files from memory.",
)
async def clear_cache() -> Dict[str, str]:
    """Clears both LRU caches safely."""
    composition_cache.clear()
    audio_cache.clear()
    return {"status": "cleared", "message": "All backend caches flushed successfully."}
