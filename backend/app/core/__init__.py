"""
Backend core module initialization.
"""

from .config import settings
from .exceptions import (
    APIError,
    AudioValidationError,
    EmptyFileError,
    FileSizeExceededError,
    AudioDurationExceededError,
    ResourceNotFoundError,
    NotImplementedAPIError,
    api_error_handler,
    generic_exception_handler,
)
from .security import (
    sanitize_client_filename,
    validate_file_extension,
    verify_audio_magic_bytes,
    save_upload_temporarily,
)

__all__ = [
    "settings",
    "APIError",
    "AudioValidationError",
    "EmptyFileError",
    "FileSizeExceededError",
    "AudioDurationExceededError",
    "ResourceNotFoundError",
    "NotImplementedAPIError",
    "api_error_handler",
    "generic_exception_handler",
    "sanitize_client_filename",
    "validate_file_extension",
    "verify_audio_magic_bytes",
    "save_upload_temporarily",
]
