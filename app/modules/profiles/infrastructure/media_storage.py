import logging
import os
import re
import tempfile
import warnings
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from threading import BoundedSemaphore

from PIL import Image, ImageOps, UnidentifiedImageError

from app.modules.profiles.domain.media import (
    InvalidImage, MAX_DIMENSION, MAX_IMAGE_BYTES, OversizedImage,
    StorageFailure, StoredImage, UnsupportedImage,
)

logger = logging.getLogger(__name__)
KEY_PATTERN = re.compile(r"[0-9a-f]{32}\.(?:jpg|png|webp)\Z")
FORMATS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp")}
DECODER_SLOT = BoundedSemaphore(1)


class LocalImageStorage:
    def __init__(self, root):
        root = Path(root)
        if not root.is_absolute() or root.is_symlink():
            raise StorageFailure("Storage root harus direktori absolut tanpa symlink")
        self.root = root.resolve()
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageFailure("Storage tidak tersedia") from exc

    def _path(self, key):
        if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key):
            raise StorageFailure("Storage key tidak valid")
        path = self.root / key
        if path.is_symlink():
            raise StorageFailure("Symlink storage ditolak")
        return path

    @contextmanager
    def temporary_upload(self):
        try:
            with tempfile.NamedTemporaryFile(prefix=".upload-", dir=self.root) as stream:
                yield stream
        except OSError as exc:
            logger.exception("Temporary upload storage failed")
            raise StorageFailure("Storage tidak tersedia") from exc

    def save_image(self, source):
        # One bounded 4096x4096 decode per worker process at a time.
        with DECODER_SLOT:
            return self._save_image(source)

    def _save_image(self, source):
        output = None
        try:
            with self.temporary_upload() as raw:
                total = 0
                while chunk := source.read(64 * 1024):
                    total += len(chunk)
                    if total > MAX_IMAGE_BYTES:
                        raise OversizedImage("Ukuran gambar maksimal 5 MiB")
                    raw.write(chunk)
                if total == 0:
                    raise InvalidImage("File gambar kosong")
                raw.seek(0)
                # Known signatures distinguish unsupported formats from broken images.
                signature = raw.read(12)
                raw.seek(0)
                supported_signature = (
                    signature.startswith(b"\xff\xd8") or signature.startswith(b"\x89PNG\r\n\x1a\n")
                    or (signature[:4] == b"RIFF" and signature[8:12] == b"WEBP")
                )
                if not supported_signature:
                    raise UnsupportedImage("Hanya JPEG, PNG dan WebP yang didukung")
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", Image.DecompressionBombWarning)
                        with Image.open(raw) as picture:
                            image_format = picture.format
                            if image_format not in FORMATS:
                                raise UnsupportedImage("Format gambar tidak didukung")
                            width, height = picture.size
                            if not (0 < width <= MAX_DIMENSION and 0 < height <= MAX_DIMENSION):
                                raise InvalidImage("Dimensi maksimal 4096x4096")
                            if getattr(picture, "n_frames", 1) != 1:
                                raise InvalidImage("Gambar animasi tidak didukung")
                            picture.verify()
                        raw.seek(0)
                        with Image.open(raw) as picture:
                            picture.load()
                            oriented = ImageOps.exif_transpose(picture)
                            mode = "RGB" if image_format == "JPEG" else "RGBA"
                            with oriented.convert(mode) as converted:
                                # Fresh pixel-only image: no EXIF, ICC, XMP or textual metadata.
                                with Image.frombytes(mode, converted.size, converted.tobytes()) as clean:
                                    fd, output = tempfile.mkstemp(prefix=".normalized-", dir=self.root)
                                    with os.fdopen(fd, "w+b") as destination:
                                        clean.save(destination, format=image_format)
                                        destination.flush()
                                        os.fsync(destination.fileno())
                                        size = destination.tell()
                    if size > MAX_IMAGE_BYTES:
                        raise OversizedImage("Hasil normalisasi melebihi 5 MiB")
                except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
                    raise InvalidImage("Dimensi gambar tidak aman") from exc
                except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
                    if isinstance(exc, OSError) and exc.errno is not None:
                        logger.exception("Image normalization storage failed")
                        raise StorageFailure("Penyimpanan gambar gagal") from exc
                    raise InvalidImage("Gambar rusak atau tidak valid") from exc
                extension, mime = FORMATS[image_format]
                key = f"{uuid4().hex}.{extension}"
                os.replace(output, self._path(key))
                output = None
                return StoredImage(key, mime, size)
        except OSError as exc:
            logger.exception("Image storage write failed")
            raise StorageFailure("Penyimpanan gambar gagal") from exc
        finally:
            if output is not None:
                try:
                    Path(output).unlink(missing_ok=True)
                except OSError as exc:
                    logger.exception("Temporary image cleanup failed: %s", output)
                    raise StorageFailure("Pembersihan file sementara gagal") from exc

    def open(self, key):
        try:
            descriptor = os.open(self._path(key), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            return os.fdopen(descriptor, "rb")
        except OSError as exc:
            logger.exception("Cannot open media file: %s", key)
            raise StorageFailure("File media tidak tersedia") from exc

    def delete(self, key):
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError as exc:
            logger.exception("Orphan media cleanup required: %s", key)
            raise StorageFailure("Pembersihan file media gagal; perlu orphan cleanup") from exc
