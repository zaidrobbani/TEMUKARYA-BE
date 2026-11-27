import io
import logging
import os
import re
import tempfile
import warnings
from pathlib import Path
from threading import BoundedSemaphore
from typing import BinaryIO
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.modules.users.domain.avatar import (
    AVATAR_MAX_DIMENSION,
    AVATAR_MAX_STORED_BYTES,
    MAX_AVATAR_UPLOAD_BYTES,
    AvatarInvalidError,
    AvatarNotFoundError,
    AvatarStorage,
    AvatarStorageError,
    AvatarTooLargeError,
    AvatarUnsupportedError,
)

logger = logging.getLogger(__name__)
KEY_PATTERN = re.compile(r"[0-9a-f]{32}\.webp\Z")
MAX_SOURCE_DIMENSION = 4096
QUALITY_STEPS = (80, 70, 60, 50, 40)
DECODER_SLOT = BoundedSemaphore(1)


def _is_supported_signature(head: bytes) -> bool:
    return (
        head.startswith(b"\xff\xd8")
        or head.startswith(b"\x89PNG\r\n\x1a\n")
        or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
    )


class LocalAvatarStorage(AvatarStorage):
    def __init__(self, root: str | Path):
        root = Path(root)
        if not root.is_absolute() or root.is_symlink():
            raise AvatarStorageError()
        self.root = root.resolve()
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.exception("Avatar storage root unavailable")
            raise AvatarStorageError() from exc

    def _path(self, key: str) -> Path:
        if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key):
            raise AvatarNotFoundError()
        return self.root / key

    def save(self, source: BinaryIO) -> str:
        data = source.read(MAX_AVATAR_UPLOAD_BYTES + 1)
        if len(data) > MAX_AVATAR_UPLOAD_BYTES:
            raise AvatarTooLargeError()
        if not data:
            raise AvatarInvalidError("File foto kosong")
        if not _is_supported_signature(data[:12]):
            raise AvatarUnsupportedError()
        with DECODER_SLOT:
            encoded = self._normalize(data)
        key = f"{uuid4().hex}.webp"
        try:
            fd, temp = tempfile.mkstemp(prefix=".avatar-", dir=self.root)
            with os.fdopen(fd, "wb") as out:
                out.write(encoded)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp, self._path(key))
        except OSError as exc:
            logger.exception("Avatar write failed")
            raise AvatarStorageError() from exc
        return key

    def _normalize(self, data: bytes) -> bytes:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as probe:
                    if probe.format not in {"JPEG", "PNG", "WEBP"}:
                        raise AvatarUnsupportedError()
                    width, height = probe.size
                    if not (0 < width <= MAX_SOURCE_DIMENSION and 0 < height <= MAX_SOURCE_DIMENSION):
                        raise AvatarInvalidError("Dimensi foto maksimal 4096x4096")
                    if getattr(probe, "n_frames", 1) != 1:
                        raise AvatarInvalidError("Foto animasi tidak didukung")
                    probe.verify()
                with Image.open(io.BytesIO(data)) as picture:
                    picture.load()
                    oriented = ImageOps.exif_transpose(picture)
                    mode = "RGBA" if "A" in oriented.getbands() else "RGB"
                    image = oriented.convert(mode)
                    image.thumbnail((AVATAR_MAX_DIMENSION, AVATAR_MAX_DIMENSION), Image.Resampling.LANCZOS)
                    clean = Image.frombytes(mode, image.size, image.tobytes())
        except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            raise AvatarInvalidError("Dimensi foto tidak aman") from exc
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise AvatarInvalidError() from exc

        encoded = b""
        for quality in QUALITY_STEPS:
            buffer = io.BytesIO()
            clean.save(buffer, format="WEBP", quality=quality, method=6)
            encoded = buffer.getvalue()
            if len(encoded) <= AVATAR_MAX_STORED_BYTES:
                return encoded
        clean.thumbnail((AVATAR_MAX_DIMENSION // 2, AVATAR_MAX_DIMENSION // 2), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        clean.save(buffer, format="WEBP", quality=QUALITY_STEPS[-1], method=6)
        return buffer.getvalue()

    def open(self, key: str) -> BinaryIO:
        try:
            descriptor = os.open(self._path(key), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            return os.fdopen(descriptor, "rb")
        except FileNotFoundError as exc:
            raise AvatarNotFoundError() from exc
        except OSError as exc:
            logger.exception("Cannot open avatar: %s", key)
            raise AvatarStorageError() from exc

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except AvatarNotFoundError:
            return
        except OSError:
            logger.exception("Avatar cleanup required: %s", key)
