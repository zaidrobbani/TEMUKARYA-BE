from __future__ import annotations

import logging
from typing import BinaryIO
from uuid import uuid4

from app.core.exceptions import ConflictError, NotFoundError
from app.core.unit_of_work import UnitOfWork
from app.modules.profiles.domain.media import (
    ImageStorage, InvalidImage, MAX_IMAGES, MediaRepository, PortfolioMedia, StorageFailure,
)

logger = logging.getLogger(__name__)


class PortfolioMediaService:
    def __init__(self, repository: MediaRepository, storage: ImageStorage, uow: UnitOfWork):
        self.repository = repository
        self.storage = storage
        self.uow = uow

    def authorize(self, owner: str, portfolio_id: str, lock: bool = True) -> None:
        if not self.repository.owns(portfolio_id, owner, lock=lock):
            raise NotFoundError("Portfolio tidak ditemukan")

    def list(self, owner: str, portfolio_id: str) -> list[PortfolioMedia]:
        self.authorize(owner, portfolio_id)
        return self.repository.list(portfolio_id)

    def _find(self, items: list[PortfolioMedia], media_id: str) -> PortfolioMedia:
        for item in items:
            if item.id == media_id:
                return item
        raise NotFoundError("Media tidak ditemukan")

    def upload(self, owner: str, portfolio_id: str, source: BinaryIO) -> PortfolioMedia:
        items = self.list(owner, portfolio_id)
        if len(items) >= MAX_IMAGES:
            raise ConflictError("Maksimal 5 gambar per portfolio")
        stored = self.storage.save_image(source)
        try:
            result = self.repository.add(PortfolioMedia(
                id=str(uuid4()), portfolio_id=portfolio_id, storage_key=stored.key,
                mime_type=stored.mime_type, file_size_bytes=stored.size,
                sort_order=len(items), is_cover=not items,
            ))
            self.uow.commit()
            return result
        except Exception:
            try:
                self.storage.delete(stored.key)
            except Exception as cleanup_error:
                logger.exception("Upload DB failure and file cleanup failure: %s", stored.key)
                raise StorageFailure("Upload gagal; file perlu orphan cleanup") from cleanup_error
            raise

    def file(self, owner: str, portfolio_id: str, media_id: str) -> tuple[PortfolioMedia, BinaryIO]:
        item = self._find(self.list(owner, portfolio_id), media_id)
        return item, self.storage.open(item.storage_key)

    def public_file(self, portfolio_id: str, media_id: str) -> tuple[PortfolioMedia, BinaryIO]:
        item = self.repository.find(portfolio_id, media_id)
        if item is None:
            raise NotFoundError("Media portfolio tidak ditemukan")
        return item, self.storage.open(item.storage_key)

    def cover(self, owner: str, portfolio_id: str, media_id: str) -> list[PortfolioMedia]:
        items = self.list(owner, portfolio_id)
        self._find(items, media_id)
        self.repository.arrange(portfolio_id, [item.id for item in items], media_id)
        result = self.repository.list(portfolio_id)
        self.uow.commit()
        return result

    def order(self, owner: str, portfolio_id: str, ids: list[str]) -> list[PortfolioMedia]:
        items = self.list(owner, portfolio_id)
        if len(ids) != len(set(ids)) or set(ids) != {item.id for item in items}:
            raise InvalidImage("Urutan harus memuat setiap ID media portfolio tepat satu kali")
        cover = next((item.id for item in items if item.is_cover), ids[0] if ids else None)
        self.repository.arrange(portfolio_id, ids, cover)
        result = self.repository.list(portfolio_id)
        self.uow.commit()
        return result

    def _cleanup(self, items: list[PortfolioMedia]) -> None:
        failed: list[str] = []
        for item in items:
            try:
                self.storage.delete(item.storage_key)
            except Exception:
                logger.exception("Committed deletion: orphan cleanup required for %s", item.storage_key)
                failed.append(item.id)
        if failed:
            raise StorageFailure("Metadata telah dihapus; pembersihan file tertunda, perlu orphan cleanup")

    def delete(self, owner: str, portfolio_id: str, media_id: str) -> None:
        items = self.list(owner, portfolio_id)
        target = self._find(items, media_id)
        remaining = [item for item in items if item.id != media_id]
        self.repository.delete(portfolio_id, media_id)
        cover = next((item.id for item in remaining if item.is_cover), remaining[0].id if remaining else None)
        self.repository.arrange(portfolio_id, [item.id for item in remaining], cover)
        self.uow.commit()
        self._cleanup([target])

    def delete_portfolio(self, owner: str, portfolio_id: str) -> None:
        items = self.list(owner, portfolio_id)
        self.repository.delete_portfolio(portfolio_id, owner)
        self.uow.commit()
        self._cleanup(items)


class DeletePortfolioWithMedia:
    def __init__(self, service: PortfolioMediaService):
        self.service = service

    def execute(self, freelancer_id: str, portfolio_id: str) -> None:
        self.service.delete_portfolio(freelancer_id, portfolio_id)
