"""
File upload validation, audio header sniffing, path traversal defense,
and secure temporary file lifecycle management.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import AsyncGenerator, Generator, Optional, Set, Tuple

from fastapi import UploadFile

from backend.app.core.config import settings
from backend.app.core.exceptions import (
    AudioValidationError,
    EmptyFileError,
    FileSizeExceededError,
)

# Known audio file magic byte signatures
AUDIO_MAGIC_SIGNATURES = [
    # WAV: 'RIFF' .... 'WAVE'
    (b"RIFF", 0),
    # FLAC: 'fLaC'
    (b"fLaC", 0),
    # OGG: 'OggS'
    (b"OggS", 0),
    # MP3 ID3 header: 'ID3'
    (b"ID3", 0),
    # MP3 frame sync bytes: \xff\xfb, \xff\xf3, \xff\xf2
    (b"\xff\xfb", 0),
    (b"\xff\xf3", 0),
    (b"\xff\xf2", 0),
    # MP4 / M4A: contains 'ftyp' at offset 4
    (b"ftyp", 4),
]


def sanitize_client_filename(raw_filename: Optional[str]) -> str:
    """
    Sanitizes raw client filename by stripping directory paths, null bytes,
    and path traversal characters ('..', '/', '\\').
    """
    if not raw_filename:
        return "unnamed_audio.wav"

    # Take only the basename, strip null bytes
    cleaned = os.path.basename(raw_filename.replace("\x00", ""))
    cleaned = cleaned.replace("..", "").replace("/", "").replace("\\", "").strip()
    return cleaned if cleaned else "unnamed_audio.wav"


def validate_file_extension(filename: str, allowed_extensions: Optional[Set[str]] = None) -> str:
    """
    Validates that the file has an allowed audio extension.
    Returns normalized lower-case extension.
    """
    allowed = allowed_extensions or settings.allowed_extensions
    ext = os.path.splitext(filename)[1].lower()

    if not ext or ext not in allowed:
        raise AudioValidationError(
            f"Unsupported audio format '{ext}'. Allowed formats: {sorted(list(allowed))}"
        )
    return ext


def verify_audio_magic_bytes(header: bytes) -> bool:
    """
    Sniffs the first 32 bytes of the file for valid audio signatures.
    """
    if len(header) < 4:
        return False

    for sig, offset in AUDIO_MAGIC_SIGNATURES:
        if len(header) >= offset + len(sig):
            if header[offset : offset + len(sig)] == sig:
                return True

    # Check for WAV header variant: RIFF in first 4 bytes and WAVE at offset 8
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        return True

    return False


@contextlib.asynccontextmanager
async def save_upload_temporarily(
    upload_file: UploadFile,
    max_bytes: int = settings.max_upload_bytes,
) -> AsyncGenerator[Tuple[Path, str, int], None]:
    """
    Securely streams and saves an UploadFile to an ephemeral UUID temporary file.
    Validates file size ceiling and audio magic bytes.
    Guarantees file removal upon exit.

    Yields:
        (temp_file_path, sanitized_original_filename, total_bytes_written)
    """
    sanitized_filename = sanitize_client_filename(upload_file.filename)
    ext = validate_file_extension(sanitized_filename)

    # Generate isolated random UUID temporary file
    temp_dir = Path(tempfile.gettempdir()) / "ragarhythm_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file_path = temp_dir / f"upload_{uuid.uuid4().hex}{ext}"

    total_bytes = 0
    header_bytes = bytearray()
    header_checked = False

    try:
        with open(temp_file_path, "wb") as f_out:
            while True:
                chunk = await upload_file.read(64 * 1024)  # 64 KB chunks
                if not chunk:
                    break

                total_bytes += len(chunk)

                # Check max upload limit
                if total_bytes > max_bytes:
                    raise FileSizeExceededError(
                        f"Upload payload ({total_bytes} bytes) exceeds maximum limit of {max_bytes} bytes (25 MB)."
                    )

                # Collect initial bytes for magic header verification
                if not header_checked:
                    header_bytes.extend(chunk[: 64 - len(header_bytes)])
                    if len(header_bytes) >= 32:
                        if not verify_audio_magic_bytes(bytes(header_bytes)):
                            raise AudioValidationError(
                                "Invalid audio file header. The uploaded file does not appear to be a valid audio recording."
                            )
                        header_checked = True

                f_out.write(chunk)

        # Handle empty files
        if total_bytes == 0:
            raise EmptyFileError("Uploaded file is empty (0 bytes).")

        # Header check for very small files (<32 bytes)
        if not header_checked and not verify_audio_magic_bytes(bytes(header_bytes)):
            raise AudioValidationError(
                "Invalid or corrupted audio file header."
            )

        yield temp_file_path, sanitized_filename, total_bytes

    finally:
        # Guaranteed cleanup of temporary storage
        if temp_file_path.exists():
            try:
                temp_file_path.unlink()
            except Exception:
                pass
