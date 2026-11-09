"""Opt-in tests against the existing local Docker Compose MySQL schema.

Run the entire suite including this test:
    docker compose exec -T -e TEMUKARYA_MYSQL_INTEGRATION=1 api python -m pytest -q -rP

No DDL, migrations, or commits. All test rows live in one outer transaction.
The fixture checks cleanup through a new physical connection after rollback,
including when assertions or setup fail. Default test runs skip this module.
"""

import os
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from time import sleep
from uuid import uuid4

import pytest
from sqlalchemy import bindparam, create_engine, event, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.modules.profiles.domain.entities import Portfolio
from app.modules.profiles.infrastructure.repositories import SqlAlchemyPortfolioRepository


pytestmark = pytest.mark.skipif(
    os.environ.get("TEMUKARYA_MYSQL_INTEGRATION") != "1",
    reason="Opt-in local Compose MySQL test: set TEMUKARYA_MYSQL_INTEGRATION=1",
)


def reject_commit(*_):
    raise AssertionError("MySQL integration tests must never commit")


@pytest.fixture
def mysql_portfolio_sandbox():
    # Fail before connecting if opt-in is used with a nonlocal/production config.
    assert Path("/.dockerenv").exists(), "Run inside the local Compose api container"
    assert settings.APP_ENV in {"development", "test", "testing"}
    assert settings.DB_HOST == "db" and settings.DB_PORT == 3306
    assert settings.DB_NAME in {"temukarya", "temukarya_test"}

    url = URL.create(
        "mysql+pymysql", username=settings.DB_USER, password=settings.DB_PASSWORD,
        host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME,
        query={"charset": "utf8mb4"},
    )
    # Avoid the shared application engine and guarantee a fresh cleanup connection.
    engine = create_engine(url, poolclass=NullPool, echo=False)
    owners = [str(uuid4()) for _ in range(2)]
    portfolio_ids = [str(uuid4()) for _ in range(4)]
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(
                bind=connection, autoflush=False, expire_on_commit=False,
                join_transaction_mode="rollback_only",
            )
            event.listen(connection, "commit", reject_commit)
            event.listen(session, "before_commit", reject_commit)
            try:
                storage = dict(connection.execute(text("""
                    SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME IN ('users', 'freelancer_profiles', 'portfolios', 'portfolio_media')
                """)).all())
                assert storage == {
                    "users": "InnoDB", "freelancer_profiles": "InnoDB", "portfolios": "InnoDB",
                    "portfolio_media": "InnoDB",
                }, "Rollback requires transactional tables"
                version = connection.scalar(text("SELECT VERSION()"))
                assert "MariaDB" not in version, "This test targets MySQL"
                print(f"MySQL {version}: local Compose transaction started")

                # Seed only random UUIDs; users ORM still declares an integer ID,
                # while the existing MySQL schema uses CHAR(36).
                session.execute(text("""
                    INSERT INTO users (id, name, email, password_hash, role)
                    VALUES (:id, :name, :email, :password_hash, :role)
                """), [
                    dict(id=owner, name="Portfolio integration test",
                         email=f"portfolio-test-{owner}@example.invalid",
                         password_hash="integration-test-not-a-login-hash", role="FREELANCER")
                    for owner in owners
                ])
                session.execute(text("""
                    INSERT INTO freelancer_profiles (user_id, professional_title, city)
                    VALUES (:owner, :title, :city)
                """), [dict(owner=owner, title="Integration test", city="Malang") for owner in owners])

                yield SqlAlchemyPortfolioRepository(session), session, owners, portfolio_ids
            finally:
                try:
                    if transaction.is_active:
                        transaction.rollback()
                finally:
                    session.close()
        # Outer connection is closed before cleanup verification below.
    finally:
        try:
            remaining = {}
            with engine.connect() as verification:
                verification.exec_driver_sql("START TRANSACTION READ ONLY")
                try:
                    checks = {
                        "users": ("SELECT COUNT(*) FROM users WHERE id IN :owners", {"owners": owners}),
                        "freelancer_profiles": (
                            "SELECT COUNT(*) FROM freelancer_profiles WHERE user_id IN :owners",
                            {"owners": owners},
                        ),
                        "portfolios": (
                            "SELECT COUNT(*) FROM portfolios WHERE freelancer_id IN :owners OR id IN :ids",
                            {"owners": owners, "ids": portfolio_ids},
                        ),
                        "portfolio_media": (
                            "SELECT COUNT(*) FROM portfolio_media WHERE portfolio_id IN :ids",
                            {"ids": portfolio_ids},
                        ),
                    }
                    for name, (sql, params) in checks.items():
                        query = text(sql).bindparams(*[bindparam(key, expanding=True) for key in params])
                        remaining[name] = verification.scalar(query, params)
                finally:
                    verification.rollback()
            assert remaining == {"users": 0, "freelancer_profiles": 0, "portfolios": 0, "portfolio_media": 0}, remaining
            print(f"Rollback verified through a new connection: {remaining}")
        finally:
            engine.dispose()


def test_portfolio_crud_pagination_ownership_and_audit_on_mysql(mysql_portfolio_sandbox):
    repository, session, owners, portfolio_ids = mysql_portfolio_sandbox
    owner, other_owner = owners
    ignored_timestamp = datetime(1990, 1, 1)
    description = "\U0001f600" * 16383 + "abc"  # Exactly 65,535 UTF-8 bytes.
    project_url = "https://example.com/" + "a" * (1000 - len("https://example.com/"))
    saved = []
    for index, portfolio_id in enumerate(portfolio_ids):
        item = repository.add(Portfolio(
            id=portfolio_id, freelancer_id=owner if index < 3 else other_owner,
            title="T" * 180, description=description, project_url=project_url,
            created_at=ignored_timestamp, updated_at=ignored_timestamp,
        ))
        assert item.id == portfolio_id
        assert item.description == description and item.project_url == project_url
        assert item.created_at is not None and item.updated_at is not None
        assert item.created_at != ignored_timestamp
        assert item.updated_at == item.created_at
        assert item.created_at.microsecond % 1000 == 0  # DATETIME(3)
        assert repository.get_by_id(item.id, item.freelancer_id) == item
        saved.append(item)

    assert session.scalar(text("SELECT COUNT(*) FROM portfolios WHERE freelancer_id = :id"), {"id": owner}) == 3

    # Preserve server timestamps; stable Python sorting mirrors the public order,
    # including the UUID tie-breaker when inserts share the same millisecond.
    expected = sorted(saved[:3], key=lambda item: item.id)
    expected.sort(key=lambda item: item.created_at, reverse=True)
    assert repository.list_by_freelancer_id(owner, limit=2, offset=0) == expected[:2]
    assert repository.list_by_freelancer_id(owner, limit=2, offset=2) == expected[2:]
    assert repository.list_by_freelancer_id(owner, limit=2, offset=3) == []
    assert repository.list_by_freelancer_id(str(uuid4()), limit=20, offset=0) == []
    assert repository.list_by_freelancer_id(other_owner, limit=20, offset=0) == [saved[3]]

    foreign = saved[3]
    missing_id = str(uuid4())
    for target in [foreign.id, missing_id]:
        assert repository.get_by_id(target, owner) is None
        assert repository.update(replace(foreign, id=target, freelancer_id=owner, title="Unauthorized")) is None
        assert repository.delete(target, owner) is False
    assert repository.get_by_id(foreign.id, other_owner) == foreign

    # Cross a DATETIME(3) tick so ON UPDATE must produce a newer timestamp.
    sleep(0.02)
    updated = repository.update(replace(
        saved[0], title="Updated metadata", description="Updated description", project_url=None,
        created_at=ignored_timestamp, updated_at=ignored_timestamp,
    ))
    assert updated is not None
    assert updated.title == "Updated metadata"
    assert updated.description == "Updated description" and updated.project_url is None
    assert updated.created_at == saved[0].created_at
    assert updated.updated_at > saved[0].updated_at
    assert updated.updated_at.microsecond % 1000 == 0
    assert repository.get_by_id(updated.id, owner) == updated

    # MySQL reports matched rows via SQLAlchemy, even for a no-op UPDATE.
    assert repository.update(updated) == updated
    assert repository.delete(saved[1].id, owner) is True
    assert repository.get_by_id(saved[1].id, owner) is None
    assert repository.delete(saved[1].id, owner) is False
    assert repository.get_by_id(saved[2].id, owner) == saved[2]
    assert repository.get_by_id(foreign.id, other_owner) == foreign
    assert len(repository.list_by_freelancer_id(owner, limit=20, offset=0)) == 2
    assert session.in_transaction()
    print("CREATE, SELECT/LIST pagination, UPDATE/no-op, DELETE and ownership assertions passed")
