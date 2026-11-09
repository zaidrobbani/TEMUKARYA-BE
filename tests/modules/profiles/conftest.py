from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Integer, MetaData, String, Table, Text, create_engine, func,
)
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.unit_of_work import UnitOfWork
from app.modules.profiles.domain.entities import FreelancerExperience
from app.modules.profiles.infrastructure.repositories import (
    SqlAlchemyFreelancerExperienceRepository,
    SqlAlchemyPortfolioRepository,
)


@pytest.fixture
def experience_store():
    # Isolated SQLite table for executing real repository queries. MySQL-specific
    # timestamp defaults and foreign keys are outside this fixture's scope.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    metadata = MetaData()
    Table(
        "freelancer_experiences", metadata,
        Column("id", String(36), primary_key=True),
        Column("freelancer_id", String(36), nullable=False),
        Column("job_title", String(150), nullable=False),
        Column("organization_name", String(160), nullable=False),
        Column("description", Text, nullable=False),
        Column("start_date", Date, nullable=False),
        Column("end_date", Date),
        Column("created_at", DateTime, server_default=func.current_timestamp()),
        Column("updated_at", DateTime, server_default=func.current_timestamp()),
    )
    metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        repository = SqlAlchemyFreelancerExperienceRepository(session)
        for experience_id, owner, start in [
            ("own-older", "owner-1", date(2023, 1, 1)),
            ("own-newer", "owner-1", date(2024, 1, 1)),
            ("foreign", "owner-2", date(2025, 1, 1)),
        ]:
            repository.add(FreelancerExperience(
                id=experience_id, freelancer_id=owner,
                job_title="Designer", organization_name="Studio",
                description="Branding", start_date=start,
            ))
        session.commit()
        uow = MagicMock(spec=UnitOfWork)
        uow.commit.side_effect = session.commit
        yield repository, uow
    engine.dispose()


@pytest.fixture
def portfolio_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    metadata = MetaData()
    table = Table(
        "portfolios", metadata,
        Column("id", String(36), primary_key=True),
        Column("freelancer_id", String(36), nullable=False),
        Column("title", String(180), nullable=False),
        Column("description", Text, nullable=False),
        Column("project_url", String(1000)),
        Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
        Column("updated_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    )
    # Test-only SQLite schema. Production MySQL defaults/FKs are not modified.
    Table(
        "portfolio_media", metadata,
        Column("id", String(36), primary_key=True),
        Column("portfolio_id", String(36), nullable=False),
        Column("storage_key", String(500), nullable=False),
        Column("mime_type", String(100), nullable=False),
        Column("file_size_bytes", Integer, nullable=False),
        Column("uploaded_at", DateTime, server_default=func.current_timestamp()),
        Column("sort_order", Integer, nullable=False),
        Column("is_cover", Boolean, nullable=False),
    )
    metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.execute(table.insert(), [
            dict(id=identifier, freelancer_id=owner, title=identifier,
                 description="Desain branding", project_url="https://example.com/project",
                 created_at=created, updated_at=created)
            for identifier, owner, created in [
                ("own-old", "owner-1", datetime(2024, 1, 1)),
                ("own-a", "owner-1", datetime(2025, 1, 1)),
                ("own-b", "owner-1", datetime(2025, 1, 1)),
                ("foreign", "owner-2", datetime(2026, 1, 1)),
            ]
        ])
        session.commit()
        yield session
    engine.dispose()


@pytest.fixture
def portfolio_store(portfolio_session):
    repository = SqlAlchemyPortfolioRepository(portfolio_session)
    uow = MagicMock(spec=UnitOfWork)
    uow.commit.side_effect = portfolio_session.commit
    return repository, uow


@pytest.fixture
def self_profile_store():
    # Register FK target metadata, as application startup does; no users table DDL.
    import app.modules.users.infrastructure.models  # noqa: F401
    from app.modules.profiles.domain.entities import UmkmProfile, FreelancerProfile
    from app.modules.profiles.infrastructure.repositories import (
        SqlAlchemyUmkmProfileRepository, SqlAlchemyFreelancerProfileRepository,
    )

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    metadata = MetaData()
    # Only isolated test tables; MySQL defaults/unsigned limits/FKs tested separately.
    for name, columns in [
        ("umkm_profiles", [
            Column("business_name", String(160), nullable=False),
            Column("business_category", String(100), nullable=False),
            Column("business_address", String(300), nullable=False),
        ]),
        ("freelancer_profiles", [
            Column("professional_title", String(150), nullable=False), Column("bio", Text),
            Column("service_price_min", Integer), Column("service_price_max", Integer),
            Column("availability_status", String(25), nullable=False),
        ]),
    ]:
        Table(name, metadata, Column("user_id", String(36), primary_key=True), *columns,
              Column("city", String(100), nullable=False),
              Column("created_at", DateTime, server_default=func.current_timestamp()),
              Column("updated_at", DateTime, server_default=func.current_timestamp()))
    metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as session:
            repositories = {
                "umkm": SqlAlchemyUmkmProfileRepository(session),
                "freelancer": SqlAlchemyFreelancerProfileRepository(session),
            }
            for owner in ("owner-1", "owner-2"):
                repositories["umkm"].add(UmkmProfile(owner, "Business " + owner, "Food", "Jl. A", "Malang"))
                repositories["freelancer"].add(FreelancerProfile(
                    owner, "Designer " + owner, "Malang", bio="Original bio",
                    service_price_min=100, service_price_max=200,
                ))
            session.commit()
            uow = MagicMock(spec=UnitOfWork)
            uow.commit.side_effect = session.commit
            yield repositories, session, uow
    finally:
        engine.dispose()
