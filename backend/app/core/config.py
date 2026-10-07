"""
Application configuration and production runtime constants for RagaRhythm AI.
Supports environment-variable based configuration for container and Cloud Run deployment.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field, field_validator, model_validator


DEFAULT_DEV_ORIGINS: List[str] = [
    "http://localhost:8080",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]


def parse_cors_origins(raw: Optional[str], app_env: str = "development") -> List[str]:
    """
    Parses and sanitizes CORS allowed origins from comma-separated or JSON list strings.
    Rejects wildcards in production environment.
    """
    origins: List[str] = []
    if raw is None or not raw.strip():
        if app_env == "production":
            return []
        return list(DEFAULT_DEV_ORIGINS)

    raw_str = raw.strip()
    if raw_str.startswith("["):
        try:
            parsed = json.loads(raw_str)
            if isinstance(parsed, list):
                origins = [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON format for CORS_ORIGINS: {exc}") from exc
    else:
        origins = [item.strip() for item in raw_str.split(",") if item.strip()]

    # Validate against control characters / newlines
    for origin in origins:
        if any(c in origin for c in "\r\n\x00\t"):
            raise ValueError(f"CORS origin contains forbidden control characters: {origin!r}")

    # Enforce production security invariant
    if app_env == "production":
        if "*" in origins:
            raise ValueError(
                "Wildcard '*' CORS origin is strictly forbidden in production mode. "
                "Specify explicit trusted origins via CORS_ORIGINS."
            )

    return origins


class Settings(BaseModel):
    """
    Global application settings configured via environment variables or defaults.
    Ensures safe production defaults and strict configuration validation.
    """

    # Application metadata
    app_name: str = "RagaRhythm AI"
    app_version: str = "1.0.0"
    app_description: str = "Indian Classical Music Analysis & Composition API"
    api_v1_prefix: str = "/api/v1"

    # Environment & Server
    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"

    # CORS
    cors_origins: List[str] = Field(default_factory=lambda: list(DEFAULT_DEV_ORIGINS))

    # Audio limits & constraints
    max_upload_size_mb: float = 25.0
    max_upload_bytes: int = 25 * 1024 * 1024
    max_duration_seconds: float = 600.0
    target_sample_rate: int = 22050

    # Supported audio extensions & MIME types
    allowed_extensions: Set[str] = {
        ".wav",
        ".mp3",
        ".flac",
        ".ogg",
        ".m4a",
    }
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
    job_max_workers: int = 4
    job_queue_capacity: int = 50
    job_retention_limit: int = 1000
    job_retention_ttl_seconds: int = 3600

    # Google Gemini Integration (Optional)
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"

    # Backward compatibility aliases
    @property
    def allowed_origins(self) -> List[str]:
        return self.cors_origins

    @property
    def max_analysis_workers(self) -> int:
        return self.job_max_workers

    @property
    def max_queued_jobs(self) -> int:
        return self.job_queue_capacity

    @property
    def job_retention_seconds(self) -> int:
        return self.job_retention_ttl_seconds

    @property
    def max_retained_jobs(self) -> int:
        return self.job_retention_limit

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        env = v.lower().strip()
        if env not in {"development", "production", "testing", "staging"}:
            raise ValueError(
                f"Invalid APP_ENV '{v}'. Allowed environments: development, production, testing, staging."
            )
        return env

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"PORT must be between 1 and 65535, got {v}.")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        level = v.upper().strip()
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in valid_levels:
            raise ValueError(
                f"Invalid LOG_LEVEL '{v}'. Allowed levels: {', '.join(sorted(valid_levels))}."
            )
        return level

    @field_validator("max_upload_size_mb")
    @classmethod
    def validate_max_upload_size(cls, v: float) -> float:
        if not (1.0 <= v <= 500.0):
            raise ValueError(f"MAX_UPLOAD_SIZE_MB must be between 1.0 and 500.0 MB, got {v}.")
        return v

    @field_validator("job_max_workers")
    @classmethod
    def validate_job_max_workers(cls, v: int) -> int:
        if not (1 <= v <= 64):
            raise ValueError(f"JOB_MAX_WORKERS must be between 1 and 64, got {v}.")
        return v

    @field_validator("job_queue_capacity")
    @classmethod
    def validate_job_queue_capacity(cls, v: int) -> int:
        if not (1 <= v <= 10000):
            raise ValueError(f"JOB_QUEUE_CAPACITY must be between 1 and 10000, got {v}.")
        return v

    @field_validator("job_retention_limit")
    @classmethod
    def validate_job_retention_limit(cls, v: int) -> int:
        if not (1 <= v <= 100000):
            raise ValueError(f"JOB_RETENTION_LIMIT must be between 1 and 100000, got {v}.")
        return v

    @field_validator("job_retention_ttl_seconds")
    @classmethod
    def validate_job_retention_ttl(cls, v: int) -> int:
        if not (60 <= v <= 2592000):  # 1 minute to 30 days
            raise ValueError(f"JOB_RETENTION_TTL_SECONDS must be between 60 and 2592000, got {v}.")
        return v

    @model_validator(mode="after")
    def compute_derived_fields_and_validate(self) -> Settings:
        # Synchronize max_upload_bytes from max_upload_size_mb
        self.max_upload_bytes = int(self.max_upload_size_mb * 1024 * 1024)

        # Enforce CORS origin security invariants
        if self.app_env == "production":
            if "*" in self.cors_origins:
                raise ValueError(
                    "Wildcard '*' CORS origin is strictly forbidden in production mode. "
                    "Configure specific trusted domains in CORS_ORIGINS."
                )
        return self


def load_settings_from_env() -> Settings:
    """
    Constructs a validated Settings instance from system environment variables.
    """
    app_env = os.getenv("APP_ENV", "development").lower().strip()
    raw_port = os.getenv("PORT", "8080")
    try:
        port = int(raw_port)
    except ValueError:
        raise ValueError(f"Invalid integer value for PORT environment variable: '{raw_port}'")

    raw_upload_mb = os.getenv("MAX_UPLOAD_SIZE_MB", "25.0")
    try:
        max_upload_size_mb = float(raw_upload_mb)
    except ValueError:
        raise ValueError(
            f"Invalid numeric value for MAX_UPLOAD_SIZE_MB environment variable: '{raw_upload_mb}'"
        )

    raw_workers = os.getenv("JOB_MAX_WORKERS", "4")
    try:
        job_max_workers = int(raw_workers)
    except ValueError:
        raise ValueError(
            f"Invalid integer value for JOB_MAX_WORKERS environment variable: '{raw_workers}'"
        )

    raw_queue = os.getenv("JOB_QUEUE_CAPACITY", "50")
    try:
        job_queue_capacity = int(raw_queue)
    except ValueError:
        raise ValueError(
            f"Invalid integer value for JOB_QUEUE_CAPACITY environment variable: '{raw_queue}'"
        )

    raw_limit = os.getenv("JOB_RETENTION_LIMIT", "1000")
    try:
        job_retention_limit = int(raw_limit)
    except ValueError:
        raise ValueError(
            f"Invalid integer value for JOB_RETENTION_LIMIT environment variable: '{raw_limit}'"
        )

    raw_ttl = os.getenv("JOB_RETENTION_TTL_SECONDS", "3600")
    try:
        job_retention_ttl_seconds = int(raw_ttl)
    except ValueError:
        raise ValueError(
            f"Invalid integer value for JOB_RETENTION_TTL_SECONDS environment variable: '{raw_ttl}'"
        )

    cors_origins = parse_cors_origins(os.getenv("CORS_ORIGINS"), app_env=app_env)

    return Settings(
        app_env=app_env,
        host=os.getenv("HOST", "0.0.0.0"),
        port=port,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        cors_origins=cors_origins,
        max_upload_size_mb=max_upload_size_mb,
        job_max_workers=job_max_workers,
        job_queue_capacity=job_queue_capacity,
        job_retention_limit=job_retention_limit,
        job_retention_ttl_seconds=job_retention_ttl_seconds,
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
    )


# Active runtime settings singleton
settings = load_settings_from_env()
