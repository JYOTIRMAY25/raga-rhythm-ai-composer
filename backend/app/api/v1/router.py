"""
Unified API v1 router definition.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.v1.endpoints import (
    analyze,
    explain,
    generate,
    health,
    ragas,
    talas,
)

api_v1_router = APIRouter()

api_v1_router.include_router(health.router)
api_v1_router.include_router(ragas.router)
api_v1_router.include_router(talas.router)
api_v1_router.include_router(analyze.router)
api_v1_router.include_router(explain.router)
api_v1_router.include_router(generate.router)
