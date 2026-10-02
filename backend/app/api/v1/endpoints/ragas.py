"""
Raga Knowledge Base catalog endpoints.
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from backend.app.analysis.raga_detector import RAGA_KNOWLEDGE_BASE
from backend.app.core.exceptions import ResourceNotFoundError
from backend.app.schemas.raga import RagaListResponse, RagaSchema

router = APIRouter(prefix="/ragas", tags=["Ragas"])


def _format_raga_schema(raga_id: str, data: dict) -> RagaSchema:
    """Formats internal raga record into clean public schema."""
    return RagaSchema(
        id=raga_id,
        name=data.get("name", raga_id.capitalize()),
        thaat=data.get("thaat"),
        time=data.get("time"),
        mood=data.get("mood"),
        vadi=data.get("vadi"),
        samvadi=data.get("samvadi"),
        swaras=data.get("swaras", []),
        varjit=data.get("varjit", []),
        aroha=data.get("aroha", []),
        avaroha=data.get("avaroha", []),
        pakad_motifs=data.get("pakad_motifs", []),
        aliases=data.get("aliases", []),
        description=data.get("description") or f"Canonical Hindustani raga belonging to the {data.get('thaat', 'standard')} thaat.",
    )


@router.get(
    "",
    response_model=RagaListResponse,
    status_code=status.HTTP_200_OK,
    summary="Query Raga Knowledge Base",
    description="Retrieves registered Hindustani classical ragas with optional filtering by Thaat, time of day, or keyword search.",
)
async def list_ragas(
    thaat: Optional[str] = Query(None, description="Filter by parent Thaat (e.g. 'Kalyan', 'Bhairav')"),
    time: Optional[str] = Query(None, description="Filter by traditional performance prahar (e.g. 'Morning', 'Evening', 'Night')"),
    search: Optional[str] = Query(None, description="Case-insensitive text search matching raga name or aliases"),
) -> RagaListResponse:
    """
    Returns filtered raga catalog list from the verified knowledge base.
    """
    results: List[RagaSchema] = []

    for raga_id, raga_data in RAGA_KNOWLEDGE_BASE.items():
        # Filter by Thaat
        if thaat:
            r_thaat = str(raga_data.get("thaat", "")).lower()
            if thaat.strip().lower() not in r_thaat:
                continue

        # Filter by Time
        if time:
            r_time = str(raga_data.get("time", "")).lower()
            if time.strip().lower() not in r_time:
                continue

        # Search term filter
        if search:
            query = search.strip().lower()
            name_match = query in raga_data.get("name", "").lower()
            id_match = query in raga_id.lower()
            alias_match = any(query in str(a).lower() for a in raga_data.get("aliases", []))
            if not (name_match or id_match or alias_match):
                continue

        results.append(_format_raga_schema(raga_id, raga_data))

    # Sort alphabetically by raga name
    results.sort(key=lambda r: r.name)

    return RagaListResponse(
        total=len(results),
        ragas=results,
    )


@router.get(
    "/{raga_id}",
    response_model=RagaSchema,
    status_code=status.HTTP_200_OK,
    summary="Get Raga Details by ID",
    description="Retrieves full musicological specification and melodic rules for a specific raga.",
)
async def get_raga_by_id(raga_id: str) -> RagaSchema:
    """
    Looks up a specific raga by canonical ID or alias.
    """
    norm_id = raga_id.strip().lower().replace("-", "_").replace(" ", "_")

    # Direct match
    if norm_id in RAGA_KNOWLEDGE_BASE:
        return _format_raga_schema(norm_id, RAGA_KNOWLEDGE_BASE[norm_id])

    # Search aliases
    for r_id, raga_data in RAGA_KNOWLEDGE_BASE.items():
        aliases = [str(a).lower() for a in raga_data.get("aliases", [])]
        if norm_id == r_id or norm_id in aliases:
            return _format_raga_schema(r_id, raga_data)

    raise ResourceNotFoundError(
        message=f"Raga '{raga_id}' not found in knowledge base.",
        error_code="RAGA_NOT_FOUND",
    )
