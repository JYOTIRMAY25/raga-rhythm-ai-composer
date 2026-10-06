"""
Application configuration and runtime constants.
"""

from __future__ import annotations

import os
from typing import List, Optional, Set
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Global application settings configured via environment or defaults."""

    app_name: str = "RagaRhythm AI"
    app_version: str = "1.0.0"
    app_description: str = "Indian Classical Music Analysis & Composition API"
    api_v1_prefix: str = "/api/v1"
    gemini_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
    gemini_model: str = "gemini-1.5-flash"
    
    # Server & CORS
    allowed_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:8080",
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:8080",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
            "*",
        ]
    )

    # Audio limits & constraints
    max_upload_bytes: int = 25 * 1024 * 1024  # 25 Megabytes
    max_duration_seconds: float = 600.0       # 10 minutes maximum
    target_sample_rate: int = 22050           # Standardized DSP sample rate

    # Supported audio extensions
    allowed_extensions: Set[str] = {
        ".wav",
        ".mp3",
        ".flac",
        ".ogg",
        ".m4a",
    }

    # Supported audio MIME types
    allowed_mime_types: Set[str] = {
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/mpeg",
        "audio/mp3",
        "audio/flac",
        "audio/x-flac",
        "audio/ogg",
        "application/ogg",
        "audio/m4a",
        "audio/x-m4a",
        "audio/mp4",
        "application/octet-stream",
    }

    # Async Analysis Job Configuration
    max_analysis_workers: int = 4
    max_queued_jobs: int = 50
    job_retention_seconds: int = 3600  # 1 hour
    max_retained_jobs: int = 1000


settings = Settings()
