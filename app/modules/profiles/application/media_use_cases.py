import logging
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

    def authorize(self, owner, portfolio_id, lock=True):
        if not self.repository.owns(portfolio_id, owner, lock=lock):
            raise NotFoundError("Portfolio tidak ditemukan")

    def list(self, owner, portfolio_id):
        self.authorize(owner, portfolio_id)
        return self.repository.list(portfolio_id)

    def _find(self, items, media_id):
        for item in items:
            if item.id == media_id:
                return item
        raise NotFoundError("Media tidak ditemukan")

    def upload(self, owner, portfolio_id, source):
        items = self.list(owner, portfolio_id)  # Parent FOR UPDATE serializes all writers.
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
            # Filesystem and DB are not one transaction. Session teardown rolls DB back.
            try:
                self.storage.delete(stored.key)
            except Exception as cleanup_error:
                logger.exception("Upload DB failure and file cleanup failure: %s", stored.key)
                raise StorageFailure("Upload gagal; file perlu orphan cleanup") from cleanup_error
            raise

    def file(self, owner, portfolio_id, media_id):
        item = self._find(self.list(owner, portfolio_id), media_id)
        return item, self.storage.open(item.storage_key)

    def cover(self, owner, portfolio_id, media_id):
        items = self.list(owner, portfolio_id)
        self._find(items, media_id)
        self.repository.arrange(portfolio_id, [item.id for item in items], media_id)
        result = self.repository.list(portfolio_id)
        self.uow.commit()
        return result

    def order(self, owner, portfolio_id, ids):
        items = self.list(owner, portfolio_id)
        if len(ids) != len(set(ids)) or set(ids) != {item.id for item in items}:
            raise InvalidImage("Urutan harus memuat setiap ID media portfolio tepat satu kali")
        cover = next((item.id for item in items if item.is_cover), ids[0] if ids else None)
        self.repository.arrange(portfolio_id, ids, cover)
        result = self.repository.list(portfolio_id)
        self.uow.commit()
        return result

    def _cleanup(self, items):
        failed = []
        for item in items:
            try:
                self.storage.delete(item.storage_key)
            except Exception:
                logger.exception("Committed deletion: orphan cleanup required for %s", item.storage_key)
                failed.append(item.id)
        if failed:
            raise StorageFailure("Metadata telah dihapus; pembersihan file tertunda, perlu orphan cleanup")

    def delete(self, owner, portfolio_id, media_id):
        items = self.list(owner, portfolio_id)
        target = self._find(items, media_id)
        remaining = [item for item in items if item.id != media_id]
        self.repository.delete(portfolio_id, media_id)
        cover = next((item.id for item in remaining if item.is_cover), remaining[0].id if remaining else None)
        self.repository.arrange(portfolio_id, [item.id for item in remaining], cover)
        self.uow.commit()  # If this fails, all original files remain untouched.
        self._cleanup([target])

    def delete_portfolio(self, owner, portfolio_id):
        items = self.list(owner, portfolio_id)
        self.repository.delete_portfolio(portfolio_id, owner)
        self.uow.commit()
        self._cleanup(items)


class DeletePortfolioWithMedia:
    def __init__(self, service: PortfolioMediaService):
        self.service = service

    def execute(self, freelancer_id, portfolio_id):
        self.service.delete_portfolio(freelancer_id, portfolio_id)
