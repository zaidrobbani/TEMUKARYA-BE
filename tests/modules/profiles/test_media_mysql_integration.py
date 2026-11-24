import io
import os
from unittest.mock import MagicMock

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.unit_of_work import UnitOfWork
from app.modules.profiles.application.media_use_cases import PortfolioMediaService
from app.modules.profiles.domain.entities import Portfolio
from app.modules.profiles.infrastructure.media_repository import SqlAlchemyMediaRepository
from app.modules.profiles.infrastructure.media_storage import LocalImageStorage
from tests.modules.profiles.test_media_storage import image_bytes
from tests.modules.profiles.test_portfolio_mysql_integration import mysql_portfolio_sandbox

pytestmark = pytest.mark.skipif(
    os.environ.get("TEMUKARYA_MYSQL_INTEGRATION") != "1", reason="Opt-in local Compose MySQL test",
)


def test_mysql_media_transactions_ownership_cover_and_cleanup(mysql_portfolio_sandbox, tmp_path):
    portfolios, session, owners, ids = mysql_portfolio_sandbox
    portfolios.add(Portfolio(ids[0], owners[0], "Test media", "Temporary metadata"))
    portfolios.add(Portfolio(ids[1], owners[1], "Other owner", "Temporary metadata"))
    repository = SqlAlchemyMediaRepository(session)
    storage = LocalImageStorage(tmp_path)
    uow = MagicMock(spec=UnitOfWork)
    # Preserve the outer rollback-only transaction; no permanent commits.
    uow.commit.side_effect = session.flush
    service = PortfolioMediaService(repository, storage, uow)
    statements = []
    event.listen(session.bind, "before_cursor_execute", lambda conn, cursor, statement, parameters, context, many: statements.append(statement))
    try:
        items = [service.upload(owners[0], ids[0], io.BytesIO(image_bytes())) for _ in range(5)]
        assert all(item.uploaded_at is not None and item.uploaded_at.microsecond % 1000 == 0 for item in items)
        assert sum(item.is_cover for item in items) == 1
        with pytest.raises(ConflictError):
            service.upload(owners[0], ids[0], io.BytesIO(image_bytes()))
        for method in (service.file, service.cover, service.delete):
            with pytest.raises(NotFoundError):
                method(owners[1], ids[0], items[0].id)
        with pytest.raises(NotFoundError):
            service.file(owners[1], ids[1], items[0].id)
        assert any("FROM portfolios" in sql and "FOR UPDATE" in sql for sql in statements)
        assert any("FROM portfolio_media" in sql and "FOR UPDATE" in sql for sql in statements)

        # A second connection cannot acquire this parent's lock while the outer
        # transaction is active. Rows remain uncommitted throughout this test.
        with session.bind.engine.connect() as competing:
            competing.exec_driver_sql("SET SESSION innodb_lock_wait_timeout = 1")
            with Session(bind=competing) as competitor:
                with pytest.raises(OperationalError) as failure:
                    SqlAlchemyMediaRepository(competitor).owns(ids[0], owners[0])
                assert failure.value.orig.args[0] == 1205
            competing.rollback()

        selected = service.cover(owners[0], ids[0], items[-1].id)
        assert [item.id for item in selected if item.is_cover] == [items[-1].id]
        reverse_ids = [item.id for item in reversed(items)]
        ordered = service.order(owners[0], ids[0], reverse_ids)
        assert [item.id for item in ordered] == reverse_ids
        service.delete(owners[0], ids[0], items[-1].id)
        remaining = service.list(owners[0], ids[0])
        assert remaining[0].is_cover and remaining[0].id == items[-2].id
        assert [item.sort_order for item in remaining] == [0, 1, 2, 3]
        service.delete_portfolio(owners[0], ids[0])
        assert repository.list(ids[0]) == []
        assert not list(tmp_path.iterdir())
        assert portfolios.get_by_id(ids[1], owners[1]) is not None
        print("MySQL media: locks, limit, cover/order, ownership, parent delete and empty test storage verified")
    finally:
        # Cleanup test-only files even if an assertion fails before the deletion.
        for path in tmp_path.iterdir():
            storage.delete(path.name)
        assert not list(tmp_path.iterdir())
