"""
Custom domain and HTTP exceptions with RFC-compliant error mapping.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse

from backend.app.schemas.common import ErrorDetailResponse


class APIError(Exception):
    """Base API exception with error code and HTTP status code."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


class AudioValidationError(APIError):
    """Raised when uploaded audio fails format or integrity validation."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            error_code="INVALID_AUDIO_FORMAT",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class EmptyFileError(APIError):
    """Raised when uploaded file is empty (0 bytes)."""

    def __init__(self, message: str = "Audio upload is empty (0 bytes).") -> None:
        super().__init__(
            message=message,
            error_code="EMPTY_FILE",
            status_code=422,
        )


class FileSizeExceededError(APIError):
    """Raised when uploaded file exceeds max allowed size (25 MB)."""

    def __init__(self, message: str = "Audio upload exceeds maximum allowed size (25 MB).") -> None:
        super().__init__(
            message=message,
            error_code="FILE_SIZE_EXCEEDED",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )


class AudioDurationExceededError(APIError):
    """Raised when decoded audio duration exceeds 600s."""

    def __init__(self, message: str = "Audio duration exceeds maximum allowed analysis duration (10 minutes).") -> None:
        super().__init__(
            message=message,
            error_code="DURATION_EXCEEDED",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ResourceNotFoundError(APIError):
    """Raised when a requested resource (raga, tala, analysis) does not exist."""

    def __init__(self, message: str, error_code: str = "RESOURCE_NOT_FOUND") -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class NotImplementedAPIError(APIError):
    """Raised for documented endpoints planned for future release."""

    def __init__(self, message: str, endpoint: str) -> None:
        super().__init__(
            message=message,
            error_code="FEATURE_NOT_IMPLEMENTED",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            details={"endpoint": endpoint, "docs": "docs/API_SPEC.md"},
        )


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Standard handler for APIError instances."""
    payload = ErrorDetailResponse(
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details or None,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=payload.model_dump(),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler for unhandled internal exceptions to sanitize error messages."""
    payload = ErrorDetailResponse(
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred while processing the audio analysis.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=payload.model_dump(),
    )
