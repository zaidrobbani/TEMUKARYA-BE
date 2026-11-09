"""Opt-in local Compose tests: real schema, random accounts, no DDL or commits."""

import os
from dataclasses import replace
from pathlib import Path
from time import sleep
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import bindparam, create_engine, event, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.unit_of_work import UnitOfWork
from app.modules.profiles.application.dto import (
    CreateFreelancerProfileInput, CreateUmkmProfileInput,
    UpdateFreelancerProfileInput, UpdateUmkmProfileInput,
)
from app.modules.profiles.application.self_profile_use_cases import (
    GetFreelancerProfile, GetUmkmProfile, UpdateFreelancerProfile, UpdateUmkmProfile,
)
from app.modules.profiles.application.use_cases import CreateFreelancerProfile, CreateUmkmProfile
from app.modules.profiles.infrastructure.repositories import (
    SqlAlchemyFreelancerProfileRepository, SqlAlchemyUmkmProfileRepository,
)
import app.modules.users.infrastructure.models  # noqa: F401 -- FK target registration only


pytestmark = pytest.mark.skipif(
    os.environ.get("TEMUKARYA_MYSQL_INTEGRATION") != "1", reason="Opt-in local Compose MySQL test",
)


def reject_profile_test_commit(*_):
    raise AssertionError("Self-profile MySQL tests must never commit")


@pytest.fixture
def mysql_self_profile_sandbox():
    assert Path("/.dockerenv").exists(), "Run inside the local Compose api container"
    assert settings.APP_ENV in {"development", "test", "testing"}
    assert settings.DB_HOST == "db" and settings.DB_PORT == 3306
    assert settings.DB_NAME in {"temukarya", "temukarya_test"}
    engine = create_engine(URL.create(
        "mysql+pymysql", username=settings.DB_USER, password=settings.DB_PASSWORD,
        host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME,
        query={"charset": "utf8mb4"},
    ), poolclass=NullPool, echo=False)
    owners = {role: [str(uuid4()), str(uuid4())] for role in ("UMKM", "FREELANCER")}
    all_ids = owners["UMKM"] + owners["FREELANCER"]
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection, autoflush=False, expire_on_commit=False,
                              join_transaction_mode="rollback_only")
            event.listen(connection, "commit", reject_profile_test_commit)
            event.listen(session, "before_commit", reject_profile_test_commit)
            try:
                engines = dict(connection.execute(text("""
                    SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME IN ('users', 'umkm_profiles', 'freelancer_profiles')
                """)).all())
                assert engines == {name: "InnoDB" for name in ("users", "umkm_profiles", "freelancer_profiles")}
                assert "MariaDB" not in connection.scalar(text("SELECT VERSION()"))
                session.execute(text("""
                    INSERT INTO users (id, name, email, password_hash, role)
                    VALUES (:id, :name, :email, :password_hash, :role)
                """), [dict(id=owner, name="Self profile integration test", role=role,
                            email=f"self-profile-{owner}@example.invalid",
                            password_hash="integration-test-not-a-login-hash")
                       for role, identifiers in owners.items() for owner in identifiers])
                yield session, owners
            finally:
                try:
                    if transaction.is_active:
                        transaction.rollback()
                finally:
                    session.close()
    finally:
        try:
            with engine.connect() as verification:
                verification.exec_driver_sql("START TRANSACTION READ ONLY")
                try:
                    remaining = {}
                    for table, column in (("users", "id"), ("umkm_profiles", "user_id"), ("freelancer_profiles", "user_id")):
                        query = text(f"SELECT COUNT(*) FROM {table} WHERE {column} IN :ids").bindparams(bindparam("ids", expanding=True))
                        remaining[table] = verification.scalar(query, {"ids": all_ids})
                    assert remaining == {"users": 0, "umkm_profiles": 0, "freelancer_profiles": 0}, remaining
                    print(f"Self-profile rollback verified through a fresh connection: {remaining}")
                finally:
                    verification.rollback()
        finally:
            engine.dispose()


@pytest.mark.parametrize("role", ["UMKM", "FREELANCER"])
def test_mysql_self_profile_create_get_replace_ownership_and_audit(mysql_self_profile_sandbox, role):
    session, owners = mysql_self_profile_sandbox
    owner, foreign_owner = owners[role]
    uow = MagicMock(spec=UnitOfWork)
    # Production use cases invoke UoW; here flush retains the outer transaction.
    uow.commit.side_effect = session.flush
    if role == "UMKM":
        repository = SqlAlchemyUmkmProfileRepository(session)
        creator, getter, updater = CreateUmkmProfile, GetUmkmProfile, UpdateUmkmProfile
        create_data = CreateUmkmProfileInput("a" * 160, "a" * 100, "a" * 300, "a" * 100)
        update_data = UpdateUmkmProfileInput("Updated", "Food", "Jl. A", "Surabaya")
        table = "umkm_profiles"
    else:
        repository = SqlAlchemyFreelancerProfileRepository(session)
        creator, getter, updater = CreateFreelancerProfile, GetFreelancerProfile, UpdateFreelancerProfile
        create_data = CreateFreelancerProfileInput(
            "a" * 150, "a" * 100, bio="\U0001f600" * 16383 + "abc",
            service_price_min=0, service_price_max=2**64 - 1,
        )
        update_data = UpdateFreelancerProfileInput("Updated", "Surabaya", availability_status="a" * 25)
        table = "freelancer_profiles"
    own = creator(repository, uow).execute(owner, create_data)
    foreign = creator(repository, uow).execute(foreign_owner, create_data)
    assert getter(repository).execute(owner) == own
    audit_query = text(f"SELECT created_at, updated_at FROM {table} WHERE user_id = :id")
    before = session.execute(audit_query, {"id": owner}).one()
    sleep(0.02)  # Cross a DATETIME(3) tick.
    updated = updater(repository, uow).execute(owner, update_data)
    after = session.execute(audit_query, {"id": owner}).one()
    assert updated.user_id == owner and updated.city == "Surabaya"
    assert getter(repository).execute(owner) == updated
    assert getter(repository).execute(foreign_owner) == foreign
    assert after.created_at == before.created_at and after.updated_at > before.updated_at
    assert after.updated_at.microsecond % 1000 == 0
    assert updater(repository, uow).execute(owner, update_data) == updated  # MySQL matched-row semantics.
    missing = str(uuid4())
    with pytest.raises(NotFoundError):
        getter(repository).execute(missing)
    with pytest.raises(NotFoundError):
        updater(repository, uow).execute(missing, update_data)
    assert repository.update(replace(updated, user_id=missing)) is None
    assert getter(repository).execute(foreign_owner) == foreign
    if role == "FREELANCER":
        assert updated.bio is updated.service_price_min is updated.service_price_max is None
        assert updated.availability_status == "a" * 25
    assert session.in_transaction()
