
from uuid import uuid4

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError

from app.modules.applications.domain.entities import (
    ProjectApplication,
)
from app.modules.applications.infrastructure.repositories import (
    SqlAlchemyApplicationRepository,
)


UMKM_ID = "11111111-1111-4111-8111-111111111111"
OTHER_UMKM_ID = "22222222-2222-4222-8222-222222222222"

FREELANCER_ID = "33333333-3333-4333-8333-333333333333"
OTHER_FREELANCER_ID = "44444444-4444-4444-8444-444444444444"

PROJECT_ID = "55555555-5555-4555-8555-555555555555"
SECOND_PROJECT_ID = "66666666-6666-4666-8666-666666666666"
CLOSED_PROJECT_ID = "77777777-7777-4777-8777-777777777777"


@pytest.fixture
def context():
    """
    SQLite sementara untuk repository tests.

    Skema tes sengaja menggunakan DDL SQLite,
    sebab DDL production menggunakan fitur MySQL
    seperti CURRENT_TIMESTAMP(3) dan UUID().
    """

    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    with engine.begin() as connection:
        connection.execute(
            text("PRAGMA foreign_keys = ON")
        )

        connection.execute(
            text("""
                CREATE TABLE projects (
                    id CHAR(36) PRIMARY KEY,
                    umkm_id CHAR(36) NOT NULL,
                    status VARCHAR(40) NOT NULL,
                    published_at DATETIME,
                    started_at DATETIME
                )
            """)
        )

        connection.execute(
            text("""
                CREATE TABLE freelancer_profiles (
                    user_id CHAR(36) PRIMARY KEY
                )
            """)
        )

        connection.execute(
            text("""
                CREATE TABLE project_applications (
                    id CHAR(36) PRIMARY KEY,
                    project_id CHAR(36) NOT NULL
                        REFERENCES projects(id),
                    freelancer_id CHAR(36) NOT NULL
                        REFERENCES freelancer_profiles(user_id),
                    proposed_price BIGINT NOT NULL
                        CHECK(proposed_price > 0),
                    estimated_duration_days INTEGER NOT NULL
                        CHECK(estimated_duration_days > 0),
                    proposal_message TEXT NOT NULL,
                    status VARCHAR(30) NOT NULL
                        DEFAULT 'SUBMITTED',
                    submitted_at DATETIME NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT
                        uq_project_applications_project_freelancer
                    UNIQUE(project_id, freelancer_id)
                )
            """)
        )

        for freelancer_id in (
            FREELANCER_ID,
            OTHER_FREELANCER_ID,
        ):
            connection.execute(
                text("""
                    INSERT INTO freelancer_profiles(user_id)
                    VALUES (:id)
                """),
                {"id": freelancer_id},
            )

        projects = [
            (PROJECT_ID, UMKM_ID, "TERBUKA", True),
            (SECOND_PROJECT_ID, UMKM_ID, "TERBUKA", True),
            (CLOSED_PROJECT_ID, UMKM_ID, "BERJALAN", True),
        ]

        for project_id, umkm_id, status, published in projects:
            connection.execute(
                text("""
                    INSERT INTO projects (
                        id,
                        umkm_id,
                        status,
                        published_at,
                        started_at
                    )
                    VALUES (
                        :id,
                        :umkm_id,
                        :status,
                        :published_at,
                        NULL
                    )
                """),
                {
                    "id": project_id,
                    "umkm_id": umkm_id,
                    "status": status,
                    "published_at": (
                        "2026-11-02 10:00:00"
                        if published else None
                    ),
                },
            )

    try:
        with Session(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
        ) as session:
            repository = SqlAlchemyApplicationRepository(
                session
            )

            yield repository, session

    finally:
        engine.dispose()


def make_application(
    project_id=PROJECT_ID,
    freelancer_id=FREELANCER_ID,
):
    return ProjectApplication(
        id=str(uuid4()),
        project_id=project_id,
        freelancer_id=freelancer_id,
        proposed_price=1500000,
        estimated_duration_days=14,
        proposal_message="Saya siap mengerjakan proyek.",
    )


# ============================================================
# VALIDATION QUERIES
# ============================================================

def test_freelancer_profile_exists(context):
    repository, session = context

    assert repository.freelancer_profile_exists(
        FREELANCER_ID
    )

    assert not repository.freelancer_profile_exists(
        str(uuid4())
    )


def test_project_availability(context):
    repository, session = context

    assert repository.project_is_open(
        PROJECT_ID
    )

    assert not repository.project_is_open(
        CLOSED_PROJECT_ID
    )

    assert not repository.project_is_open(
        str(uuid4())
    )


def test_project_ownership(context):
    repository, session = context

    assert repository.project_owned_by_umkm(
        PROJECT_ID,
        UMKM_ID,
    )

    assert not repository.project_owned_by_umkm(
        PROJECT_ID,
        OTHER_UMKM_ID,
    )


# ============================================================
# CREATE & READ
# ============================================================

def test_add_and_get_application(context):
    repository, session = context

    application = make_application()

    saved = repository.add(application)

    assert saved.id == application.id
    assert saved.project_id == PROJECT_ID
    assert saved.freelancer_id == FREELANCER_ID
    assert saved.status == "SUBMITTED"
    assert saved.proposed_price == 1500000
    assert saved.submitted_at is not None

    found = repository.get_by_id(application.id)

    assert found is not None
    assert found.id == application.id


def test_missing_application_returns_none(context):
    repository, session = context

    assert repository.get_by_id(
        str(uuid4())
    ) is None


def test_get_by_project_and_freelancer(context):
    repository, session = context

    application = make_application()
    repository.add(application)

    found = repository.get_by_project_and_freelancer(
        PROJECT_ID,
        FREELANCER_ID,
    )

    assert found is not None
    assert found.id == application.id

    missing = repository.get_by_project_and_freelancer(
        PROJECT_ID,
        OTHER_FREELANCER_ID,
    )

    assert missing is None


# ============================================================
# DATABASE CONSTRAINTS
# ============================================================

def test_duplicate_application_returns_conflict(context):
    repository, session = context

    repository.add(make_application())

    with pytest.raises(ConflictError):
        repository.add(make_application())


def test_application_is_not_auto_committed(context):
    repository, session = context

    application = make_application()
    repository.add(application)

    session.rollback()

    assert repository.get_by_id(application.id) is None


# ============================================================
# LISTING & ISOLATION
# ============================================================

def test_list_by_freelancer(context):
    repository, session = context

    repository.add(
        make_application(
            project_id=PROJECT_ID,
            freelancer_id=FREELANCER_ID,
        )
    )

    repository.add(
        make_application(
            project_id=SECOND_PROJECT_ID,
            freelancer_id=FREELANCER_ID,
        )
    )

    repository.add(
        make_application(
            project_id=PROJECT_ID,
            freelancer_id=OTHER_FREELANCER_ID,
        )
    )

    results = repository.list_by_freelancer(
        freelancer_id=FREELANCER_ID,
        limit=10,
        offset=0,
    )

    assert len(results) == 2

    assert all(
        item.freelancer_id == FREELANCER_ID
        for item in results
    )


def test_list_by_project(context):
    repository, session = context

    repository.add(
        make_application(
            project_id=PROJECT_ID,
            freelancer_id=FREELANCER_ID,
        )
    )

    repository.add(
        make_application(
            project_id=PROJECT_ID,
            freelancer_id=OTHER_FREELANCER_ID,
        )
    )

    repository.add(
        make_application(
            project_id=SECOND_PROJECT_ID,
            freelancer_id=FREELANCER_ID,
        )
    )

    results = repository.list_by_project(
        project_id=PROJECT_ID,
        limit=10,
        offset=0,
    )

    assert len(results) == 2

    assert all(
        item.project_id == PROJECT_ID
        for item in results
    )


def test_listing_pagination(context):
    repository, session = context

    repository.add(
        make_application(
            project_id=PROJECT_ID,
            freelancer_id=FREELANCER_ID,
        )
    )

    repository.add(
        make_application(
            project_id=SECOND_PROJECT_ID,
            freelancer_id=FREELANCER_ID,
        )
    )

    first = repository.list_by_freelancer(
        freelancer_id=FREELANCER_ID,
        limit=1,
        offset=0,
    )

    second = repository.list_by_freelancer(
        freelancer_id=FREELANCER_ID,
        limit=1,
        offset=1,
    )

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].id != second[0].id
