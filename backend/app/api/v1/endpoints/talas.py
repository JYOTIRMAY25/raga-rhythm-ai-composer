"""
Tala Knowledge Base catalog endpoints.
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Query, status

from backend.app.analysis.tala_knowledge_base import (
    TALA_KNOWLEDGE_BASE,
    TalaDefinition,
    get_all_talas,
    get_tala,
)
from backend.app.core.exceptions import ResourceNotFoundError
from backend.app.schemas.tala import TalaListResponse, TalaSchema

router = APIRouter(prefix="/talas", tags=["Talas"])


def _format_tala_schema(tala_def: TalaDefinition) -> TalaSchema:
    """Formats internal TalaDefinition into clean public schema."""
    vibhag_str = "+".join(str(v) for v in tala_def.vibhag_structure)
    theka_str = " ".join(tala_def.theka_syllables)
    
    # Construct pattern representation with vibhag bars
    pattern_parts = []
    idx = 0
    for v in tala_def.vibhag_structure:
        pattern_parts.append(" ".join(tala_def.theka_syllables[idx : idx + v]))
        idx += v
    pattern_str = " | ".join(pattern_parts)

    return TalaSchema(
        id=tala_def.tala_id,
        name=tala_def.name,
        matras=tala_def.matras,
        beats=tala_def.matras,
        vibhag_structure=list(tala_def.vibhag_structure),
        vibhag=vibhag_str,
        sam_position=tala_def.sam_position,
        khali_positions=list(tala_def.khali_positions),
        tali_positions=list(tala_def.tali_positions),
        theka=theka_str,
        pattern=pattern_str,
        theka_syllables=list(tala_def.theka_syllables),
        aliases=list(tala_def.aliases),
        description=tala_def.description or f"Canonical Hindustani {tala_def.matras}-beat rhythmic cycle.",
    )


@router.get(
    "",
    response_model=TalaListResponse,
    status_code=status.HTTP_200_OK,
    summary="Query Tala Knowledge Base",
    description="Retrieves registered Hindustani classical rhythmic cycles with optional filtering by matra count or keyword search.",
)
async def list_talas(
    matras: Optional[int] = Query(None, ge=1, description="Filter by exact cycle beat count (e.g. 16, 12, 10, 8, 7, 6)"),
    search: Optional[str] = Query(None, description="Case-insensitive text search matching tala name or aliases"),
) -> TalaListResponse:
    """
    Returns filtered tala catalog list from the verified knowledge base.
    """
    all_defs = get_all_talas()
    results: List[TalaSchema] = []

    for tala_def in all_defs:
        if matras is not None and tala_def.matras != matras:
            continue

        if search:
            query = search.strip().lower()
            name_match = query in tala_def.name.lower()
            id_match = query in tala_def.tala_id.lower()
            alias_match = any(query in str(a).lower() for a in tala_def.aliases)
            if not (name_match or id_match or alias_match):
                continue

        results.append(_format_tala_schema(tala_def))

    # Sort ascending by matras, then alphabetically by name
    results.sort(key=lambda t: (t.matras, t.name))

    return TalaListResponse(
        total=len(results),
        talas=results,
    )


@router.get(
    "/{tala_id}",
    response_model=TalaSchema,
    status_code=status.HTTP_200_OK,
    summary="Get Tala Details by ID",
    description="Retrieves full rhythmic specification, vibhag divisions, and theka syllables for a specific tala.",
)
async def get_tala_by_id(tala_id: str) -> TalaSchema:
    """
    Looks up a specific tala by canonical ID or alias.
    """
    tala_def = get_tala(tala_id)
    if not tala_def:
        raise ResourceNotFoundError(
            message=f"Tala '{tala_id}' not found in knowledge base.",
            error_code="TALA_NOT_FOUND",
        )
    return _format_tala_schema(tala_def)
