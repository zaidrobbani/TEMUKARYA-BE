from abc import ABC, abstractmethod
from typing import BinaryIO

from app.core.exceptions import BadRequestError, NotFoundError, PayloadTooLargeError, ServiceUnavailableError, UnsupportedMediaTypeError

MAX_AVATAR_UPLOAD_BYTES = 2 * 1024 * 1024
AVATAR_MAX_DIMENSION = 512
AVATAR_MAX_STORED_BYTES = 150 * 1024
AVATAR_MIME_TYPE = "image/webp"


class AvatarTooLargeError(PayloadTooLargeError):
    def __init__(self) -> None:
        super().__init__("Ukuran foto maksimal 2 MB")


class AvatarUnsupportedError(UnsupportedMediaTypeError):
    def __init__(self) -> None:
        super().__init__("Format foto harus JPG, PNG, atau WebP")


class AvatarInvalidError(BadRequestError):
    def __init__(self, message: str = "Foto rusak atau tidak dapat dibaca") -> None:
        super().__init__(message)


class AvatarNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Foto profil tidak ditemukan")


class AvatarStorageError(ServiceUnavailableError):
    def __init__(self) -> None:
        super().__init__("Penyimpanan foto sedang tidak tersedia, silakan coba lagi")


class AvatarStorage(ABC):
    @abstractmethod
    def save(self, source: BinaryIO) -> str: ...

    @abstractmethod
    def open(self, key: str) -> BinaryIO: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


def avatar_url(api_prefix: str, user_id: str, key: str) -> str:
    return f"{api_prefix}/users/{user_id}/photo?v={key.removesuffix('.webp')}"


def avatar_key_from_url(url: str | None) -> str | None:
    if not url or "?v=" not in url:
        return None
    version = url.rsplit("?v=", 1)[1]
    return f"{version}.webp" if version else None
