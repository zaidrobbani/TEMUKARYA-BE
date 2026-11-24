from dataclasses import replace
from datetime import datetime

import pytest
from sqlalchemy import event, text

from app.modules.profiles.domain.entities import Portfolio


def test_portfolio_insert_uses_database_timestamps_and_can_rollback(portfolio_store, portfolio_session):
    repository, _ = portfolio_store
    statements = []
    event.listen(portfolio_session.bind, "before_cursor_execute", lambda conn, cursor, statement, parameters, context, many: statements.append(statement))
    saved = repository.add(Portfolio(
        "new", "owner-1", "Title", "Description", created_at=datetime(1990, 1, 1),
        updated_at=datetime(1990, 1, 1),
    ))
    assert saved.created_at is not None and saved.created_at != datetime(1990, 1, 1)
    assert saved.updated_at == saved.created_at
    inserted_columns = next(sql for sql in statements if sql.startswith("INSERT")).split("VALUES")[0]
    assert "created_at" not in inserted_columns and "updated_at" not in inserted_columns
    assert repository.get_by_id("new", "owner-1") == saved
    portfolio_session.rollback()
    assert repository.get_by_id("new", "owner-1") is None


def test_portfolio_list_paginates_after_owner_filter_with_stable_order(portfolio_store):
    repository, _ = portfolio_store
    assert [row.id for row in repository.list_by_freelancer_id("owner-1", 2, 0)] == ["own-a", "own-b"]
    assert [row.id for row in repository.list_by_freelancer_id("owner-1", 2, 2)] == ["own-old"]
    assert repository.list_by_freelancer_id("owner-1", 2, 3) == []
    assert repository.list_by_freelancer_id("empty", 2, 0) == []


@pytest.mark.parametrize("target", ["foreign", "missing", "' OR 1=1 --"])
def test_portfolio_repository_blocks_foreign_and_missing_ids(portfolio_store, target):
    repository, uow = portfolio_store
    original = repository.get_by_id("foreign", "owner-2")
    assert repository.get_by_id(target, "owner-1") is None
    assert repository.update(Portfolio(target, "owner-1", "Changed", "Changed")) is None
    assert repository.delete(target, "owner-1") is False
    uow.commit()
    assert repository.get_by_id("foreign", "owner-2") == original
    assert len(repository.list_by_freelancer_id("owner-1", 10, 0)) == 3


def test_portfolio_update_refreshes_server_timestamps_without_assigning_them(portfolio_store, portfolio_session):
    repository, uow = portfolio_store
    # A test-only trigger simulates a server-generated update timestamp.
    portfolio_session.execute(text("""
        CREATE TRIGGER portfolio_timestamp AFTER UPDATE ON portfolios
        BEGIN UPDATE portfolios SET updated_at = '2030-01-01 00:00:00'
        WHERE id = NEW.id; END
    """))
    original = repository.get_by_id("own-a", "owner-1")
    saved = repository.update(replace(
        original, title="Updated", project_url=None,
        created_at=datetime(1990, 1, 1), updated_at=datetime(1990, 1, 1),
    ))
    assert saved.title == "Updated" and saved.project_url is None
    assert saved.created_at == original.created_at
    assert saved.updated_at == datetime(2030, 1, 1)
    uow.commit()
    assert repository.get_by_id("own-a", "owner-1") == saved
    assert repository.update(saved) == saved
    assert repository.get_by_id("foreign", "owner-2").title == "foreign"


def test_portfolio_delete_is_scoped_and_transactional(portfolio_store, portfolio_session):
    repository, uow = portfolio_store
    assert repository.delete("own-a", "owner-1") is True
    portfolio_session.rollback()
    assert repository.get_by_id("own-a", "owner-1") is not None
    assert repository.delete("own-a", "owner-1") is True
    uow.commit()
    assert repository.delete("own-a", "owner-1") is False
    assert repository.get_by_id("own-b", "owner-1") is not None
    assert repository.get_by_id("foreign", "owner-2") is not None
