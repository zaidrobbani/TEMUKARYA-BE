from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO

from app.core.exceptions import BadRequestError, NotFoundError, PayloadTooLargeError, ServiceUnavailableError, UnsupportedMediaTypeError
from app.modules.chat.domain.message_rules import MAX_FILE_BYTES

# Foto chat (gaya WhatsApp ringan): disimpan WebP, sisi terpanjang maks 1600 px, <= 400 KB, plus thumbnail 320 px.
CHAT_IMAGE_MAX_DIMENSION = 1600
CHAT_IMAGE_MAX_BYTES = 400 * 1024
CHAT_THUMBNAIL_DIMENSION = 320
CHAT_THUMBNAIL_MAX_BYTES = 30 * 1024
# Batas unggahan foto mentah sebelum dikompres server (Android sudah mengompres lebih dulu).
CHAT_IMAGE_UPLOAD_MAX_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class StoredChatFile:
    key: str
    mime_type: str
    size: int
    thumbnail_key: str | None = None


class ChatFileTooLargeError(PayloadTooLargeError):
    def __init__(self) -> None:
        super().__init__(f"Ukuran lampiran maksimal {MAX_FILE_BYTES // (1024 * 1024)} MB")


class ChatFileUnsupportedError(UnsupportedMediaTypeError):
    def __init__(self, message: str = "Format lampiran tidak didukung") -> None:
        super().__init__(message)


class ChatFileInvalidError(BadRequestError):
    def __init__(self, message: str = "Lampiran rusak atau tidak dapat dibaca") -> None:
        super().__init__(message)


class ChatFileNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Lampiran tidak ditemukan")


class ChatFileStorageError(ServiceUnavailableError):
    def __init__(self) -> None:
        super().__init__("Penyimpanan lampiran sedang tidak tersedia, silakan coba lagi")


def thumbnail_key_of(key: str) -> str | None:
    """Thumbnail hanya dibuat untuk foto (`<hex>.webp` → `<hex>.thumb.webp`), jadi tidak perlu kolom DB baru."""
    if key.endswith(".webp") and not key.endswith(".thumb.webp"):
        return key.removesuffix(".webp") + ".thumb.webp"
    return None


class ChatAttachmentStorage(ABC):
    @abstractmethod
    def save_image(self, source: BinaryIO) -> StoredChatFile: ...

    @abstractmethod
    def save_document(self, source: BinaryIO, file_name: str) -> StoredChatFile: ...

    @abstractmethod
    def open(self, key: str) -> BinaryIO: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...
