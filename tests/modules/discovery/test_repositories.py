import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.modules.discovery.domain.entities import (
    FreelancerSearchFilters,
)

from app.modules.discovery.infrastructure.repositories import (
    SqlAlchemyDiscoveryRepository,
)


# ============================================================
# SQLITE TEST DATABASE FIXTURE
# ============================================================

@pytest.fixture
def context():
    """
    Database SQLite sementara khusus unit test.

    Tidak menggunakan MySQL production/development.
    Tidak mengubah data TEMUKARYA sungguhan.
    """

    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    with engine.begin() as connection:

        # ====================================================
        # CREATE MINIMAL TEST TABLES
        # ====================================================

        statements = [
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                email TEXT,
                password_hash TEXT
            )
            """,
            """
            CREATE TABLE freelancer_profiles (
                user_id TEXT PRIMARY KEY,
                professional_title TEXT NOT NULL,
                bio TEXT,
                city TEXT NOT NULL,
                availability_status TEXT NOT NULL,
                service_price_min INTEGER,
                service_price_max INTEGER
            )
            """,
            """
            CREATE TABLE skills (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE freelancer_skills (
                freelancer_id TEXT NOT NULL,
                skill_id TEXT NOT NULL,
                PRIMARY KEY (freelancer_id, skill_id)
            )
            """,
            """
            CREATE TABLE freelancer_experiences (
                id TEXT PRIMARY KEY,
                freelancer_id TEXT NOT NULL,
                job_title TEXT,
                organization_name TEXT,
                description TEXT,
                start_date TEXT,
                end_date TEXT
            )
            """,
            """
            CREATE TABLE portfolios (
                id TEXT PRIMARY KEY,
                freelancer_id TEXT NOT NULL,
                title TEXT,
                description TEXT,
                project_url TEXT,
                created_at TEXT
            )
            """,
            """
            CREATE TABLE project_agreements (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL UNIQUE,
                freelancer_id TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE freelancer_reviews (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL UNIQUE,
                rating INTEGER NOT NULL,
                review_text TEXT,
                created_at TEXT
            )
            """,
        ]

        for statement in statements:
            connection.execute(text(statement))

        # ====================================================
        # SEED USERS
        # ====================================================

        connection.execute(
            text("""
                INSERT INTO users
                    (id, name, role, email, password_hash)
                VALUES
                    (:id, :name, :role, :email, :password_hash)
            """),
            [
                {
                    "id": "f1",
                    "name": "Andi",
                    "role": "freelancer",
                    "email": "hidden-andi@example.org",
                    "password_hash": "secret",
                },
                {
                    "id": "f2",
                    "name": "Budi",
                    "role": "freelancer",
                    "email": "hidden-budi@example.org",
                    "password_hash": "secret",
                },
                {
                    "id": "f3",
                    "name": "Cici",
                    "role": "freelancer",
                    "email": "hidden-cici@example.org",
                    "password_hash": "secret",
                },
                {
                    "id": "f4",
                    "name": "Dina",
                    "role": "freelancer",
                    "email": "hidden-dina@example.org",
                    "password_hash": "secret",
                },
                {
                    "id": "u1",
                    "name": "Owner",
                    "role": "umkm",
                    "email": "owner@example.org",
                    "password_hash": "secret",
                },
            ],
        )

        # ====================================================
        # SEED FREELANCER PROFILES
        # ====================================================

        connection.execute(
            text("""
                INSERT INTO freelancer_profiles (
                    user_id,
                    professional_title,
                    bio,
                    city,
                    availability_status,
                    service_price_min,
                    service_price_max
                )
                VALUES (
                    :user_id,
                    :professional_title,
                    :bio,
                    :city,
                    :availability_status,
                    :service_price_min,
                    :service_price_max
                )
            """),
            [
                {
                    "user_id": "f1",
                    "professional_title": "Backend Developer",
                    "bio": "Backend specialist",
                    "city": "Malang",
                    "availability_status": "AVAILABLE",
                    "service_price_min": 500000,
                    "service_price_max": 2000000,
                },
                {
                    "user_id": "f2",
                    "professional_title": "Graphic Designer",
                    "bio": "Visual designer",
                    "city": "Bandung",
                    "availability_status": "AVAILABLE",
                    "service_price_min": 200000,
                    "service_price_max": 600000,
                },
                {
                    "user_id": "f3",
                    "professional_title": "Web Engineer",
                    "bio": "Busy freelancer",
                    "city": "Malang",
                    "availability_status": "BUSY",
                    "service_price_min": 1000000,
                    "service_price_max": 3000000,
                },
                {
                    "user_id": "f4",
                    "professional_title": "UI Designer",
                    "bio": "New freelancer",
                    "city": "Malang",
                    "availability_status": "AVAILABLE",
                    "service_price_min": None,
                    "service_price_max": None,
                },
                {
                    "user_id": "u1",
                    "professional_title": "Never shown",
                    "bio": "role=umkm",
                    "city": "Malang",
                    "availability_status": "AVAILABLE",
                    "service_price_min": 100,
                    "service_price_max": 200,
                },
            ],
        )

        # ====================================================
        # SEED SKILLS
        # ====================================================

        connection.execute(
            text("""
                INSERT INTO skills (id, name)
                VALUES (:id, :name)
            """),
            [
                {"id": "py", "name": "Python"},
                {"id": "api", "name": "FastAPI"},
                {"id": "design", "name": "Graphic Design"},
            ],
        )

        connection.execute(
            text("""
                INSERT INTO freelancer_skills (
                    freelancer_id,
                    skill_id
                )
                VALUES (
                    :freelancer_id,
                    :skill_id
                )
            """),
            [
                {"freelancer_id": "f1", "skill_id": "py"},
                {"freelancer_id": "f1", "skill_id": "api"},
                {"freelancer_id": "f2", "skill_id": "design"},
                {"freelancer_id": "f3", "skill_id": "py"},
            ],
        )

        # ====================================================
        # SEED EXPERIENCES
        # ====================================================

        connection.execute(
            text("""
                INSERT INTO freelancer_experiences (
                    id,
                    freelancer_id,
                    job_title,
                    organization_name,
                    description,
                    start_date,
                    end_date
                )
                VALUES (
                    :id,
                    :freelancer_id,
                    :job_title,
                    :organization_name,
                    :description,
                    :start_date,
                    :end_date
                )
            """),
            [
                {
                    "id": "e1",
                    "freelancer_id": "f1",
                    "job_title": "Backend Dev",
                    "organization_name": "Studio",
                    "description": "API",
                    "start_date": "2024-01-01",
                    "end_date": None,
                },
                {
                    "id": "e2",
                    "freelancer_id": "f1",
                    "job_title": "Engineer",
                    "organization_name": "Shop",
                    "description": "Backend",
                    "start_date": "2025-01-01",
                    "end_date": "2026-01-01",
                },
                {
                    "id": "e3",
                    "freelancer_id": "f2",
                    "job_title": "Designer",
                    "organization_name": "Agency",
                    "description": "Brand",
                    "start_date": "2025-01-01",
                    "end_date": None,
                },
            ],
        )

        # ====================================================
        # SEED PORTFOLIOS
        # ====================================================

        connection.execute(
            text("""
                INSERT INTO portfolios (
                    id,
                    freelancer_id,
                    title,
                    description,
                    project_url,
                    created_at
                )
                VALUES (
                    :id,
                    :freelancer_id,
                    :title,
                    :description,
                    :project_url,
                    :created_at
                )
            """),
            [
                {
                    "id": "po1",
                    "freelancer_id": "f1",
                    "title": "Store API",
                    "description": "E-commerce",
                    "project_url": "https://example.org",
                    "created_at": "2026-11-01 00:00:00",
                },
                {
                    "id": "po2",
                    "freelancer_id": "f1",
                    "title": "Backend CMS",
                    "description": "CMS",
                    "project_url": None,
                    "created_at": "2026-10-01 00:00:00",
                },
            ],
        )

        # ====================================================
        # SEED AGREEMENTS
        # ====================================================

        connection.execute(
            text("""
                INSERT INTO project_agreements (
                    id,
                    project_id,
                    freelancer_id
                )
                VALUES (
                    :id,
                    :project_id,
                    :freelancer_id
                )
            """),
            [
                {
                    "id": "a1",
                    "project_id": "p1",
                    "freelancer_id": "f1",
                },
                {
                    "id": "a2",
                    "project_id": "p2",
                    "freelancer_id": "f1",
                },
                {
                    "id": "a3",
                    "project_id": "p3",
                    "freelancer_id": "f2",
                },
            ],
        )

        # ====================================================
        # SEED REVIEWS
        # ====================================================

        connection.execute(
            text("""
                INSERT INTO freelancer_reviews (
                    id,
                    project_id,
                    rating,
                    review_text,
                    created_at
                )
                VALUES (
                    :id,
                    :project_id,
                    :rating,
                    :review_text,
                    :created_at
                )
            """),
            [
                {
                    "id": "r1",
                    "project_id": "p1",
                    "rating": 5,
                    "review_text": "Great",
                    "created_at": "2026-10-01 10:00:00",
                },
                {
                    "id": "r2",
                    "project_id": "p2",
                    "rating": 4,
                    "review_text": "Nice",
                    "created_at": "2026-10-02 10:00:00",
                },
                {
                    "id": "r3",
                    "project_id": "p3",
                    "rating": 3,
                    "review_text": "Okay",
                    "created_at": "2026-10-03 10:00:00",
                },
            ],
        )

    try:
        with Session(engine) as session:
            repository = SqlAlchemyDiscoveryRepository(
                session
            )
            yield repository, session

    finally:
        engine.dispose()


# ============================================================
# SEARCH HELPER
# ============================================================

def search(repo, **kwargs):
    return repo.search_freelancers(
        filters=FreelancerSearchFilters(**kwargs),
        limit=50,
        offset=0,
    )


# ============================================================
# 1. DEFAULT LISTING
# ============================================================

def test_default_listing_and_no_duplicates(context):
    repository, session = context

    results = search(repository)

    assert [item.user_id for item in results] == [
        "f1",
        "f2",
        "f4",
    ]

    assert len({
        item.user_id for item in results
    }) == 3

    assert [item.name for item in results] == [
        "Andi",
        "Budi",
        "Dina",
    ]


# ============================================================
# 2. NO CREDENTIAL EXPOSURE
# ============================================================

def test_user_credentials_not_exposed(context):
    from dataclasses import asdict

    repository, session = context

    data = repr([
        asdict(item)
        for item in search(repository)
    ])

    assert "hidden-andi" not in data
    assert "secret" not in data
    assert "password_hash" not in data


# ============================================================
# 3. SEARCH BY NAME / PROFESSION / SKILL
# ============================================================

def test_search_by_name_profession_or_skill(context):
    repository, session = context

    assert [
        item.user_id
        for item in search(
            repository,
            search="ANDI",
        )
    ] == ["f1"]

    assert [
        item.user_id
        for item in search(
            repository,
            search="graphic",
        )
    ] == ["f2"]

    assert [
        item.user_id
        for item in search(
            repository,
            search="FastAPI",
        )
    ] == ["f1"]


# ============================================================
# 4. SKILL FILTER
# ============================================================

def test_skills_match_any_without_duplication(context):
    repository, session = context

    results = search(
        repository,
        skill_ids=("py", "api", "design"),
    )

    assert [
        item.user_id
        for item in results
    ] == ["f1", "f2"]

    assert [
        skill.name
        for skill in results[0].skills
    ] == [
        "FastAPI",
        "Python",
    ]


# ============================================================
# 5. CITY & AVAILABILITY FILTER
# ============================================================

def test_city_and_availability_filters(context):
    repository, session = context

    assert [
        item.user_id
        for item in search(
            repository,
            city="malang",
        )
    ] == ["f1", "f4"]

    assert [
        item.user_id
        for item in search(
            repository,
            availability_status="BUSY",
        )
    ] == ["f3"]

    assert [
        item.user_id
        for item in search(
            repository,
            availability_status=None,
        )
    ] == [
        "f1",
        "f2",
        "f3",
        "f4",
    ]


# ============================================================
# 6. PRICE RANGE FILTER
# ============================================================

def test_price_range_overlap_and_missing_prices(
    context,
):
    repository, session = context

    assert [
        item.user_id
        for item in search(
            repository,
            min_price=550000,
            max_price=1000000,
        )
    ] == ["f1", "f2"]

    assert [
        item.user_id
        for item in search(
            repository,
            min_price=800000,
        )
    ] == ["f1"]

    assert [
        item.user_id
        for item in search(
            repository,
            max_price=300000,
        )
    ] == ["f2"]


# ============================================================
# 7. EXPERIENCE & RATING FILTER
# ============================================================

def test_experience_count_and_rating(context):
    repository, session = context

    assert [
        item.user_id
        for item in search(
            repository,
            min_experience_count=2,
        )
    ] == ["f1"]

    assert [
        item.user_id
        for item in search(
            repository,
            min_rating=4.0,
        )
    ] == ["f1"]

    assert [
        item.user_id
        for item in search(
            repository,
            min_rating=0,
        )
    ] == ["f1", "f2"]

    first = search(repository)[0]

    assert first.experience_count == 2
    assert first.review_count == 2
    assert first.average_rating == 4.5

    assert search(repository)[-1].average_rating is None


# ============================================================
# 8. PAGINATION
# ============================================================

def test_pagination_deterministic(context):
    repository, session = context

    filters = FreelancerSearchFilters()

    first = repository.search_freelancers(
        filters=filters,
        limit=1,
        offset=0,
    )

    second = repository.search_freelancers(
        filters=filters,
        limit=1,
        offset=1,
    )

    assert first[0].name == "Andi"
    assert second[0].name == "Budi"


# ============================================================
# 9. FREELANCER DETAIL
# ============================================================

def test_detail_includes_related_data(context):
    repository, session = context

    detail = repository.get_freelancer_detail("f1")

    assert detail is not None
    assert detail.user_id == "f1"
    assert detail.bio == "Backend specialist"

    assert len(detail.skills) == 2

    assert len(detail.experiences) == 2
    assert detail.experiences[0].job_title == "Engineer"
    assert detail.experiences[0].end_date.year == 2026

    assert len(detail.portfolios) == 2
    assert detail.portfolios[0].title == "Store API"

    assert len(detail.reviews) == 2
    assert detail.reviews[0].rating == 4

    assert detail.average_rating == 4.5


# ============================================================
# 10. NONEXISTENT PROFILE / WRONG ROLE
# ============================================================

def test_detail_unknown_and_wrong_role(context):
    repository, session = context

    assert repository.get_freelancer_detail(
        "does-not-exist"
    ) is None

    assert repository.get_freelancer_detail(
        "u1"
    ) is None


# ============================================================
# 11. BUSY FREELANCER DETAIL
# ============================================================

def test_detail_available_even_if_busy(context):
    repository, session = context

    detail = repository.get_freelancer_detail("f3")

    assert detail is not None
    assert detail.availability_status == "BUSY"


# ============================================================
# 12. SEARCH WILDCARDS & SQL INJECTION
# ============================================================

def test_like_wildcards_are_literal(context):
    repository, session = context

    assert search(
        repository,
        search="%",
    ) == []

    assert search(
        repository,
        search="_",
    ) == []

    assert search(
        repository,
        search="%' OR 1=1 --",
    ) == []


# ============================================================
# 13. READ-ONLY BEHAVIOR
# ============================================================

def test_read_only_repository(context):
    repository, session = context

    before = session.execute(
        text("""
            SELECT COUNT(*)
            FROM freelancer_profiles
        """)
    ).scalar_one()

    repository.search_freelancers(
        filters=FreelancerSearchFilters(),
        limit=20,
        offset=0,
    )

    repository.get_freelancer_detail("f1")

    after = session.execute(
        text("""
            SELECT COUNT(*)
            FROM freelancer_profiles
        """)
    ).scalar_one()

    assert before == after