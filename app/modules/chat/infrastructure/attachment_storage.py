import io
import logging
import os
import re
import tempfile
import warnings
import zipfile
from pathlib import Path
from threading import BoundedSemaphore
from typing import BinaryIO
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.modules.chat.domain.attachment_storage import (
    CHAT_IMAGE_MAX_BYTES,
    CHAT_IMAGE_MAX_DIMENSION,
    CHAT_IMAGE_UPLOAD_MAX_BYTES,
    CHAT_THUMBNAIL_DIMENSION,
    CHAT_THUMBNAIL_MAX_BYTES,
    ChatAttachmentStorage,
    ChatFileInvalidError,
    ChatFileNotFoundError,
    ChatFileStorageError,
    ChatFileTooLargeError,
    ChatFileUnsupportedError,
    StoredChatFile,
)
from app.modules.chat.domain.message_rules import MAX_FILE_BYTES

logger = logging.getLogger(__name__)
KEY_PATTERN = re.compile(r"[0-9a-f]{32}(?:\.thumb)?\.(?:webp|pdf|txt|csv|zip|docx|xlsx|pptx)\Z")
MAX_SOURCE_DIMENSION = 8192
QUALITY_STEPS = (80, 70, 60, 50, 40)
DECODER_SLOT = BoundedSemaphore(1)

OOXML = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
OOXML_MARKERS = {"docx": "word/", "xlsx": "xl/", "pptx": "ppt/"}
EXECUTABLE_SIGNATURES = (b"MZ", b"\x7fELF", b"\xca\xfe\xba\xbe", b"\xcf\xfa\xed\xfe", b"#!")


def _is_image_signature(head: bytes) -> bool:
    return (
        head.startswith(b"\xff\xd8")
        or head.startswith(b"\x89PNG\r\n\x1a\n")
        or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
    )


class LocalChatAttachmentStorage(ChatAttachmentStorage):
    def __init__(self, root: str | Path):
        root = Path(root)
        if not root.is_absolute() or root.is_symlink():
            raise ChatFileStorageError()
        self.root = root.resolve()
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.exception("Chat attachment storage root unavailable")
            raise ChatFileStorageError() from exc

    def _path(self, key: str) -> Path:
        if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key):
            raise ChatFileNotFoundError()
        return self.root / key

    def _write(self, key: str, data: bytes) -> None:
        try:
            fd, temp = tempfile.mkstemp(prefix=".chat-", dir=self.root)
            with os.fdopen(fd, "wb") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp, self._path(key))
        except OSError as exc:
            logger.exception("Chat attachment write failed")
            raise ChatFileStorageError() from exc

    @staticmethod
    def _read_limited(source: BinaryIO, limit: int) -> bytes:
        data = source.read(limit + 1)
        if len(data) > limit:
            raise ChatFileTooLargeError()
        if not data:
            raise ChatFileInvalidError("File lampiran kosong")
        return data

    def save_image(self, source: BinaryIO) -> StoredChatFile:
        data = self._read_limited(source, CHAT_IMAGE_UPLOAD_MAX_BYTES)
        if not _is_image_signature(data[:12]):
            raise ChatFileUnsupportedError("Foto harus JPG, PNG, atau WebP")
        with DECODER_SLOT:
            full, thumb = self._compress(data)
        hex_id = uuid4().hex
        key, thumb_key = f"{hex_id}.webp", f"{hex_id}.thumb.webp"
        self._write(key, full)
        try:
            self._write(thumb_key, thumb)
        except Exception:
            self.delete(key)
            raise
        return StoredChatFile(key=key, mime_type="image/webp", size=len(full), thumbnail_key=thumb_key)

    def _compress(self, data: bytes) -> tuple[bytes, bytes]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as probe:
                    if probe.format not in {"JPEG", "PNG", "WEBP"}:
                        raise ChatFileUnsupportedError("Foto harus JPG, PNG, atau WebP")
                    width, height = probe.size
                    if not (0 < width <= MAX_SOURCE_DIMENSION and 0 < height <= MAX_SOURCE_DIMENSION):
                        raise ChatFileInvalidError("Dimensi foto terlalu besar")
                    if getattr(probe, "n_frames", 1) != 1:
                        raise ChatFileInvalidError("Foto animasi tidak didukung")
                    probe.verify()
                with Image.open(io.BytesIO(data)) as picture:
                    picture.load()
                    oriented = ImageOps.exif_transpose(picture)
                    mode = "RGBA" if "A" in oriented.getbands() else "RGB"
                    converted = oriented.convert(mode)
                    clean = Image.frombytes(mode, converted.size, converted.tobytes())
        except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            raise ChatFileInvalidError("Dimensi foto tidak aman") from exc
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise ChatFileInvalidError() from exc

        full = clean.copy()
        full.thumbnail((CHAT_IMAGE_MAX_DIMENSION, CHAT_IMAGE_MAX_DIMENSION), Image.Resampling.LANCZOS)
        thumb = clean.copy()
        thumb.thumbnail((CHAT_THUMBNAIL_DIMENSION, CHAT_THUMBNAIL_DIMENSION), Image.Resampling.LANCZOS)
        return self._encode(full, CHAT_IMAGE_MAX_BYTES), self._encode(thumb, CHAT_THUMBNAIL_MAX_BYTES)

    @staticmethod
    def _encode(image: Image.Image, max_bytes: int) -> bytes:
        encoded = b""
        for quality in QUALITY_STEPS:
            buffer = io.BytesIO()
            image.save(buffer, format="WEBP", quality=quality, method=6)
            encoded = buffer.getvalue()
            if len(encoded) <= max_bytes:
                return encoded
        smaller = image.copy()
        smaller.thumbnail((max(1, image.width // 2), max(1, image.height // 2)), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        smaller.save(buffer, format="WEBP", quality=QUALITY_STEPS[-1], method=6)
        return buffer.getvalue()

    def save_document(self, source: BinaryIO, file_name: str) -> StoredChatFile:
        data = self._read_limited(source, MAX_FILE_BYTES)
        mime, extension = self._detect_document(data, file_name)
        key = f"{uuid4().hex}.{extension}"
        self._write(key, data)
        return StoredChatFile(key=key, mime_type=mime, size=len(data))

    @staticmethod
    def _detect_document(data: bytes, file_name: str) -> tuple[str, str]:
        if any(data.startswith(signature) for signature in EXECUTABLE_SIGNATURES):
            raise ChatFileUnsupportedError("File program tidak boleh dikirim")
        extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if data.startswith(b"%PDF-"):
            return "application/pdf", "pdf"
        if _is_image_signature(data[:12]):
            raise ChatFileUnsupportedError("Kirim foto lewat Galeri/Kamera")
        if data.startswith(b"PK\x03\x04"):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    names = archive.namelist()
            except zipfile.BadZipFile as exc:
                raise ChatFileInvalidError() from exc
            if extension in OOXML:
                if not any(name.startswith(OOXML_MARKERS[extension]) for name in names):
                    raise ChatFileInvalidError("Isi file tidak sesuai dengan formatnya")
                return OOXML[extension], extension
            return "application/zip", "zip"
        if extension in {"txt", "csv"}:
            try:
                data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ChatFileUnsupportedError("File teks harus berenkode UTF-8") from exc
            return ("text/csv", "csv") if extension == "csv" else ("text/plain", "txt")
        raise ChatFileUnsupportedError("Format dokumen didukung: PDF, Word, Excel, PowerPoint, TXT, CSV, ZIP")

    def open(self, key: str) -> BinaryIO:
        try:
            descriptor = os.open(self._path(key), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            return os.fdopen(descriptor, "rb")
        except FileNotFoundError as exc:
            raise ChatFileNotFoundError() from exc
        except OSError as exc:
            logger.exception("Cannot open chat attachment: %s", key)
            raise ChatFileStorageError() from exc

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except ChatFileNotFoundError:
            return
        except OSError:
            logger.exception("Chat attachment cleanup required: %s", key)
