import io
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.core.unit_of_work import UnitOfWork
from app.modules.profiles.application.media_use_cases import PortfolioMediaService
from app.modules.profiles.domain.media import InvalidImage, StorageFailure
from app.modules.profiles.infrastructure.media_repository import SqlAlchemyMediaRepository
from app.modules.profiles.infrastructure.media_storage import LocalImageStorage
from tests.modules.profiles.test_media_storage import image_bytes


@pytest.fixture
def media_service(portfolio_session, tmp_path):
    repository = SqlAlchemyMediaRepository(portfolio_session)
    storage = LocalImageStorage(tmp_path)
    uow = MagicMock(spec=UnitOfWork)
    uow.commit.side_effect = portfolio_session.commit
    return PortfolioMediaService(repository, storage, uow)


def upload(service, portfolio="own-a", owner="owner-1"):
    return service.upload(owner, portfolio, io.BytesIO(image_bytes()))


def test_cover_order_delete_and_parent_cleanup(media_service):
    service = media_service
    first, second, third = [upload(service) for _ in range(3)]
    assert first.is_cover and not second.is_cover
    ordered = service.order("owner-1", "own-a", [third.id, first.id, second.id])
    assert [item.sort_order for item in ordered] == [0, 1, 2]
    service.cover("owner-1", "own-a", second.id)
    assert [item.id for item in service.list("owner-1", "own-a") if item.is_cover] == [second.id]
    service.delete("owner-1", "own-a", second.id)
    remaining = service.list("owner-1", "own-a")
    assert remaining[0].id == third.id and remaining[0].is_cover
    assert not (service.storage.root / second.storage_key).exists()
    service.delete_portfolio("owner-1", "own-a")
    assert not list(service.storage.root.iterdir())
    assert not service.repository.owns("own-a", "owner-1")


def test_limit_is_checked_before_writing(media_service):
    for _ in range(5):
        upload(media_service)
    with pytest.raises(ConflictError):
        upload(media_service)
    assert len(list(media_service.storage.root.iterdir())) == 5
    assert sum(item.is_cover for item in media_service.list("owner-1", "own-a")) == 1


@pytest.mark.parametrize("order", [[], ["other"], ["duplicate", "duplicate"]])
def test_invalid_order_does_not_commit(media_service, order):
    original = upload(media_service)
    media_service.uow.commit.reset_mock()
    with pytest.raises(InvalidImage):
        media_service.order("owner-1", "own-a", order)
    media_service.uow.commit.assert_not_called()
    assert media_service.list("owner-1", "own-a") == [original]


@pytest.mark.parametrize("operation", ["file", "cover", "delete"])
def test_cross_portfolio_media_is_not_found(media_service, operation):
    item = upload(media_service, "own-b")
    with pytest.raises(NotFoundError):
        getattr(media_service, operation)("owner-1", "own-a", item.id)
    assert (media_service.storage.root / item.storage_key).exists()


def test_failed_upload_commit_removes_file_and_rolls_back_rows(media_service, portfolio_session):
    media_service.uow.commit.side_effect = RuntimeError("DB failed")
    with pytest.raises(RuntimeError):
        upload(media_service)
    portfolio_session.rollback()
    assert media_service.repository.list("own-a") == []
    assert not list(media_service.storage.root.iterdir())


@pytest.mark.parametrize("parent", [False, True])
def test_failed_delete_commit_preserves_files_and_rows(media_service, portfolio_session, parent):
    item = upload(media_service)
    media_service.uow.commit.side_effect = RuntimeError("DB failed")
    with pytest.raises(RuntimeError):
        if parent:
            media_service.delete_portfolio("owner-1", "own-a")
        else:
            media_service.delete("owner-1", "own-a", item.id)
    portfolio_session.rollback()
    assert (media_service.storage.root / item.storage_key).exists()
    assert media_service.list("owner-1", "own-a") == [item]


def test_cleanup_failure_is_reported_after_committed_delete(media_service, monkeypatch):
    item = upload(media_service)
    def fail(key):
        raise StorageFailure("disk denied")
    monkeypatch.setattr(media_service.storage, "delete", fail)
    with pytest.raises(StorageFailure, match="Metadata telah dihapus"):
        media_service.delete("owner-1", "own-a", item.id)
    assert media_service.repository.list("own-a") == []
    assert (media_service.storage.root / item.storage_key).exists()


def test_failed_upload_cleanup_is_not_silent(media_service, monkeypatch):
    media_service.uow.commit.side_effect = RuntimeError("DB failed")
    def fail(key):
        raise StorageFailure("disk denied")
    monkeypatch.setattr(media_service.storage, "delete", fail)
    with pytest.raises(StorageFailure, match="orphan cleanup"):
        upload(media_service)
    assert len(list(media_service.storage.root.iterdir())) == 1
