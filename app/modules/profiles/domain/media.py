from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO, ContextManager, Protocol

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES = 5
MAX_DIMENSION = 4096


class MediaError(Exception):
    pass


class OversizedImage(MediaError):
    pass


class UnsupportedImage(MediaError):
    pass


class InvalidImage(MediaError):
    pass


class StorageFailure(MediaError):
    pass


@dataclass(frozen=True)
class StoredImage:
    key: str
    mime_type: str
    size: int


@dataclass(frozen=True)
class PortfolioMedia:
    id: str
    portfolio_id: str
    storage_key: str
    mime_type: str
    file_size_bytes: int
    sort_order: int
    is_cover: bool
    uploaded_at: datetime | None = None


class ImageStorage(Protocol):
    def temporary_upload(self) -> ContextManager[BinaryIO]: ...
    def save_image(self, source: BinaryIO) -> StoredImage: ...
    def open(self, key: str) -> BinaryIO: ...
    def delete(self, key: str) -> None: ...


class MediaRepository(Protocol):
    def owns(self, portfolio_id: str, owner: str, lock: bool = True) -> bool: ...
    def list(self, portfolio_id: str) -> list[PortfolioMedia]: ...
    def add(self, media: PortfolioMedia) -> PortfolioMedia: ...
    def arrange(self, portfolio_id: str, ids: list[str], cover_id: str | None) -> None: ...
    def delete(self, portfolio_id: str, media_id: str) -> None: ...
    def delete_portfolio(self, portfolio_id: str, owner: str) -> None: ...
