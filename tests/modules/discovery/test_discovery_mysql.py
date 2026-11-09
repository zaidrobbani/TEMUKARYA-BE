import os

from dataclasses import asdict
from datetime import date, timedelta
from uuid import uuid4

import pytest

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine

from app.modules.discovery.domain.entities import (
    FreelancerSearchFilters,
)

from app.modules.discovery.infrastructure.repositories import (
    SqlAlchemyDiscoveryRepository,
)


# ============================================================
# MYSQL TEST CONFIGURATION
# ============================================================

@pytest.fixture
def mysql_engine():
    """
    Jalankan MySQL test hanya jika diaktifkan
    secara eksplisit dan menggunakan database
    TEMUKARYA lokal.
    """

    if os.getenv("TEMUKARYA_RUN_MYSQL_TESTS") != "1":
        pytest.skip("MySQL integration test disabled")

    if engine.url.get_backend_name() != "mysql":
        pytest.skip("Database bukan MySQL")

    if engine.url.host not in (
        "localhost",
        "127.0.0.1",
        "db",
    ):
        pytest.skip("Host database tidak diizinkan")

    if engine.url.database != "temukarya":
        pytest.skip("Nama database tidak sesuai")

    if settings.APP_ENV.lower() in (
        "production",
        "prod",
    ):
        pytest.skip("Production database is not allowed")

    return engine


# ============================================================
# DATABASE HELPER
# ============================================================

def insert_rows(session, statement, rows):
    """
    Membantu INSERT data sementara menggunakan
    SQL terparameter.
    """

    session.execute(
        text(statement),
        rows,
    )


# ============================================================
# MYSQL INTEGRATION TEST
# ============================================================

def test_discovery_mysql_integration(mysql_engine):
    """
    Memeriksa Discovery Repository terhadap
    skema MySQL TEMUKARYA yang sebenarnya.

    Seluruh INSERT berjalan dalam satu transaksi
    dan akan di-rollback pada akhir pengujian.
    """

    tag = uuid4().hex[:12]

    umkm_id = str(uuid4())

    freelancer_a = str(uuid4())
    freelancer_b = str(uuid4())
    freelancer_c = str(uuid4())

    skill_python = f"disc-py-{tag}"
    skill_fastapi = f"disc-api-{tag}"
    skill_design = f"disc-design-{tag}"

    category_id = f"disc-cat-{tag}"

    project_a = str(uuid4())
    project_b = str(uuid4())

    review_a = str(uuid4())
    review_b = str(uuid4())

    user_ids = (
        umkm_id,
        freelancer_a,
        freelancer_b,
        freelancer_c,
    )

    project_ids = (
        project_a,
        project_b,
    )

    skill_ids = (
        skill_python,
        skill_fastapi,
        skill_design,
    )

    connection = mysql_engine.connect()
    transaction = connection.begin()

    try:
        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
        ) as session:

            # =================================================
            # 1. VERIFY USERS ID CONTRACT
            # =================================================

            id_type = session.execute(
                text("""
                    SELECT DATA_TYPE
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'users'
                      AND COLUMN_NAME = 'id'
                """)
            ).scalar_one()

            if id_type.lower() not in (
                "char",
                "varchar",
            ):
                pytest.fail(
                    "Kontrak ID database belum sinkron: "
                    "users.id bukan UUID CHAR/VARCHAR. "
                    "Koordinasikan migrasi Users/Auth "
                    "bersama Zaid sebelum integration test."
                )

            # =================================================
            # 2. TEMPORARY USERS
            # =================================================

            users = [
                {
                    "id": umkm_id,
                    "name": f"Discovery {tag} Owner",
                    "role": "umkm",
                },
                {
                    "id": freelancer_a,
                    "name": f"Discovery {tag} Andi",
                    "role": "freelancer",
                },
                {
                    "id": freelancer_b,
                    "name": f"Discovery {tag} Budi",
                    "role": "freelancer",
                },
                {
                    "id": freelancer_c,
                    "name": f"Discovery {tag} Cici",
                    "role": "freelancer",
                },
            ]

            insert_rows(
                session,
                """
                    INSERT INTO users (
                        id, name, email,
                        password_hash, role
                    )
                    VALUES (
                        :id, :name, :email,
                        :password_hash, :role
                    )
                """,
                [
                    {
                        **user,
                        "email": (
                            f"discovery-{user['id']}"
                            "@example.invalid"
                        ),
                        "password_hash": "test-only",
                    }
                    for user in users
                ],
            )

            # =================================================
            # 3. TEMPORARY UMKM PROFILE
            # =================================================

            insert_rows(
                session,
                """
                    INSERT INTO umkm_profiles (
                        user_id,
                        business_name,
                        business_category,
                        business_address,
                        city
                    )
                    VALUES (
                        :user_id,
                        :business_name,
                        :business_category,
                        :business_address,
                        :city
                    )
                """,
                {
                    "user_id": umkm_id,
                    "business_name": f"Discovery Test {tag}",
                    "business_category": "Technology",
                    "business_address": "Test Address",
                    "city": "Malang",
                },
            )

            # =================================================
            # 4. TEMPORARY FREELANCER PROFILES
            # =================================================

            profiles = [
                {
                    "user_id": freelancer_a,
                    "professional_title": "Backend Developer",
                    "bio": "Python and FastAPI developer",
                    "city": "Malang",
                    "availability_status": "AVAILABLE",
                    "service_price_min": 500000,
                    "service_price_max": 2000000,
                },
                {
                    "user_id": freelancer_b,
                    "professional_title": "Graphic Designer",
                    "bio": "Brand identity designer",
                    "city": "Bandung",
                    "availability_status": "AVAILABLE",
                    "service_price_min": 200000,
                    "service_price_max": 600000,
                },
                {
                    "user_id": freelancer_c,
                    "professional_title": "Web Developer",
                    "bio": "Currently unavailable",
                    "city": "Malang",
                    "availability_status": "BUSY",
                    "service_price_min": None,
                    "service_price_max": None,
                },
            ]

            insert_rows(
                session,
                """
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
                """,
                profiles,
            )

            # =================================================
            # 5. TEMPORARY SKILLS
            # =================================================

            insert_rows(
                session,
                """
                    INSERT INTO skills (id, name)
                    VALUES (:id, :name)
                """,
                [
                    {
                        "id": skill_python,
                        "name": f"Discovery Python {tag}",
                    },
                    {
                        "id": skill_fastapi,
                        "name": f"Discovery FastAPI {tag}",
                    },
                    {
                        "id": skill_design,
                        "name": f"Discovery Design {tag}",
                    },
                ],
            )

            insert_rows(
                session,
                """
                    INSERT INTO freelancer_skills (
                        freelancer_id,
                        skill_id
                    )
                    VALUES (
                        :freelancer_id,
                        :skill_id
                    )
                """,
                [
                    {
                        "freelancer_id": freelancer_a,
                        "skill_id": skill_python,
                    },
                    {
                        "freelancer_id": freelancer_a,
                        "skill_id": skill_fastapi,
                    },
                    {
                        "freelancer_id": freelancer_b,
                        "skill_id": skill_design,
                    },
                ],
            )

            # =================================================
            # 6. TEMPORARY EXPERIENCES
            # =================================================

            insert_rows(
                session,
                """
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
                """,
                [
                    {
                        "id": str(uuid4()),
                        "freelancer_id": freelancer_a,
                        "job_title": "Backend Developer",
                        "organization_name": "Tech Studio",
                        "description": "Develop REST APIs",
                        "start_date": date(2024, 1, 1),
                        "end_date": None,
                    },
                    {
                        "id": str(uuid4()),
                        "freelancer_id": freelancer_a,
                        "job_title": "Software Engineer",
                        "organization_name": "Digital Agency",
                        "description": "Build backend services",
                        "start_date": date(2025, 1, 1),
                        "end_date": date(2026, 1, 1),
                    },
                ],
            )

            # =================================================
            # 7. TEMPORARY PORTFOLIO
            # =================================================

            insert_rows(
                session,
                """
                    INSERT INTO portfolios (
                        id,
                        freelancer_id,
                        title,
                        description,
                        project_url
                    )
                    VALUES (
                        :id,
                        :freelancer_id,
                        :title,
                        :description,
                        :project_url
                    )
                """,
                {
                    "id": str(uuid4()),
                    "freelancer_id": freelancer_a,
                    "title": "MySQL Discovery Portfolio",
                    "description": "Backend API project",
                    "project_url": "https://example.org",
                },
            )

            # =================================================
            # 8. TEMPORARY PROJECT CATEGORY
            # =================================================

            insert_rows(
                session,
                """
                    INSERT INTO project_categories (
                        id,
                        name,
                        description,
                        is_active
                    )
                    VALUES (
                        :id,
                        :name,
                        :description,
                        1
                    )
                """,
                {
                    "id": category_id,
                    "name": f"Discovery Category {tag}",
                    "description": "Temporary test category",
                },
            )

            # =================================================
            # 9. TEMPORARY PROJECTS
            # =================================================

            insert_rows(
                session,
                """
                    INSERT INTO projects (
                        id,
                        umkm_id,
                        category_id,
                        title,
                        description,
                        budget,
                        deadline,
                        status
                    )
                    VALUES (
                        :id,
                        :umkm_id,
                        :category_id,
                        :title,
                        :description,
                        :budget,
                        :deadline,
                        :status
                    )
                """,
                [
                    {
                        "id": project_id,
                        "umkm_id": umkm_id,
                        "category_id": category_id,
                        "title": f"Discovery Review Project {i}",
                        "description": "Temporary testing project",
                        "budget": 1500000,
                        "deadline": (
                            date.today()
                            + timedelta(days=30)
                        ),
                        "status": "SELESAI",
                    }
                    for i, project_id in enumerate(
                        project_ids, start=1
                    )
                ],
            )

            # =================================================
            # 10. TEMPORARY AGREEMENTS
            # =================================================

            insert_rows(
                session,
                """
                    INSERT INTO project_agreements (
                        id,
                        project_id,
                        freelancer_id,
                        selection_source,
                        scope_of_work,
                        agreed_price,
                        agreed_deadline
                    )
                    VALUES (
                        :id,
                        :project_id,
                        :freelancer_id,
                        :selection_source,
                        :scope_of_work,
                        :agreed_price,
                        :agreed_deadline
                    )
                """,
                [
                    {
                        "id": str(uuid4()),
                        "project_id": project_id,
                        "freelancer_id": freelancer_a,
                        "selection_source": "SEARCH",
                        "scope_of_work": "Backend development",
                        "agreed_price": 1000000,
                        "agreed_deadline": (
                            date.today()
                            + timedelta(days=30)
                        ),
                    }
                    for project_id in project_ids
                ],
            )

            # =================================================
            # 11. TEMPORARY REVIEWS
            # =================================================

            insert_rows(
                session,
                """
                    INSERT INTO freelancer_reviews (
                        id,
                        project_id,
                        rating,
                        review_text
                    )
                    VALUES (
                        :id,
                        :project_id,
                        :rating,
                        :review_text
                    )
                """,
                [
                    {
                        "id": review_a,
                        "project_id": project_a,
                        "rating": 5,
                        "review_text": "Excellent",
                    },
                    {
                        "id": review_b,
                        "project_id": project_b,
                        "rating": 4,
                        "review_text": "Good",
                    },
                ],
            )

            # =================================================
            # 12. START DISCOVERY REPOSITORY
            # =================================================

            repository = SqlAlchemyDiscoveryRepository(
                session
            )

            def find(**filters):
                return repository.search_freelancers(
                    filters=FreelancerSearchFilters(
                        search=tag,
                        **filters,
                    ),
                    limit=20,
                    offset=0,
                )

            # =================================================
            # 13. DEFAULT SEARCH
            # =================================================

            results = find()

            assert len(results) == 2

            assert [
                item.user_id for item in results
            ] == [
                freelancer_a,
                freelancer_b,
            ]

            assert len({
                item.user_id for item in results
            }) == 2

            print("\nDEFAULT FREELANCER SEARCH: OK")

            # =================================================
            # 14. SEARCH BY NAME / SKILL
            # =================================================

            name_results = repository.search_freelancers(
                filters=FreelancerSearchFilters(
                    search=f"Discovery {tag} Andi",
                ),
                limit=10,
                offset=0,
            )

            assert [
                item.user_id for item in name_results
            ] == [freelancer_a]

            skill_results = repository.search_freelancers(
                filters=FreelancerSearchFilters(
                    search=f"Discovery Python {tag}",
                ),
                limit=10,
                offset=0,
            )

            assert [
                item.user_id for item in skill_results
            ] == [freelancer_a]

            print("NAME AND SKILL SEARCH: OK")

            # =================================================
            # 15. SKILL FILTER
            # =================================================

            filtered = find(
                skill_ids=(
                    skill_python,
                    skill_fastapi,
                ),
            )

            assert [
                item.user_id for item in filtered
            ] == [freelancer_a]

            assert len(filtered[0].skills) == 2

            print("SKILL FILTER: OK")

            # =================================================
            # 16. CITY FILTER
            # =================================================

            city_results = find(city="Malang")

            assert [
                item.user_id for item in city_results
            ] == [freelancer_a]

            print("CITY FILTER: OK")

            # =================================================
            # 17. AVAILABILITY FILTER
            # =================================================

            busy_results = find(
                availability_status="BUSY",
            )

            assert [
                item.user_id for item in busy_results
            ] == [freelancer_c]

            print("AVAILABILITY FILTER: OK")

            # =================================================
            # 18. PRICE FILTER
            # =================================================

            price_results = find(
                min_price=700000,
                max_price=2500000,
            )

            assert [
                item.user_id for item in price_results
            ] == [freelancer_a]

            print("PRICE RANGE FILTER: OK")

            # =================================================
            # 19. EXPERIENCE FILTER
            # =================================================

            experience_results = find(
                min_experience_count=2,
            )

            assert [
                item.user_id for item in experience_results
            ] == [freelancer_a]

            print("EXPERIENCE FILTER: OK")

            # =================================================
            # 20. RATING FILTER
            # =================================================

            rated_results = find(
                min_rating=4.0,
            )

            assert [
                item.user_id for item in rated_results
            ] == [freelancer_a]

            assert rated_results[0].average_rating == 4.5
            assert rated_results[0].review_count == 2

            print("MYSQL RATING CALCULATION: OK")

            # =================================================
            # 21. PAGINATION
            # =================================================

            page_1 = repository.search_freelancers(
                filters=FreelancerSearchFilters(
                    search=tag
                ),
                limit=1,
                offset=0,
            )

            page_2 = repository.search_freelancers(
                filters=FreelancerSearchFilters(
                    search=tag
                ),
                limit=1,
                offset=1,
            )

            assert len(page_1) == 1
            assert len(page_2) == 1

            assert page_1[0].user_id != page_2[0].user_id

            print("MYSQL PAGINATION: OK")

            # =================================================
            # 22. FREELANCER DETAIL
            # =================================================

            detail = repository.get_freelancer_detail(
                freelancer_a
            )

            assert detail is not None
            assert detail.name.endswith("Andi")
            assert detail.bio == (
                "Python and FastAPI developer"
            )

            assert len(detail.skills) == 2
            assert len(detail.experiences) == 2
            assert len(detail.portfolios) == 1
            assert len(detail.reviews) == 2

            assert detail.average_rating == 4.5

            print("FREELANCER DETAIL: OK")

            # =================================================
            # 23. FREELANCER WITHOUT REVIEWS
            # =================================================

            no_reviews = repository.get_freelancer_detail(
                freelancer_b
            )

            assert no_reviews is not None
            assert no_reviews.average_rating is None
            assert no_reviews.review_count == 0
            assert no_reviews.reviews == ()

            print("FREELANCER WITHOUT REVIEW: OK")

            # =================================================
            # 24. INVALID FREELANCER
            # =================================================

            assert repository.get_freelancer_detail(
                str(uuid4())
            ) is None

            assert repository.get_freelancer_detail(
                umkm_id
            ) is None

            print("UNKNOWN / WRONG ROLE: OK")

            # =================================================
            # 25. SENSITIVE DATA PROTECTION
            # =================================================

            public_data = asdict(detail)

            assert "email" not in public_data
            assert "password_hash" not in public_data
            assert "password" not in public_data

            print("SENSITIVE DATA PROTECTION: OK")

    finally:
        # ====================================================
        # 26. ROLLBACK TEMPORARY DATA
        # ====================================================

        transaction.rollback()
        connection.close()

        print("MYSQL TRANSACTION ROLLBACK: EXECUTED")

    # ========================================================
    # 27. VERIFY CLEANUP
    # ========================================================

    with mysql_engine.connect() as check_connection:

        checks = [
            ("users", "id", user_ids),
            (
                "freelancer_profiles",
                "user_id",
                (
                    freelancer_a,
                    freelancer_b,
                    freelancer_c,
                ),
            ),
            ("umkm_profiles", "user_id", (umkm_id,)),
            ("skills", "id", skill_ids),
            (
                "project_categories",
                "id",
                (category_id,),
            ),
            ("projects", "id", project_ids),
            (
                "freelancer_reviews",
                "id",
                (review_a, review_b),
            ),
        ]

        for table, column, identifiers in checks:

            for identifier in identifiers:

                remaining = check_connection.execute(
                    text(
                        f"SELECT COUNT(*) FROM {table} "
                        f"WHERE {column} = :identifier"
                    ),
                    {"identifier": identifier},
                ).scalar_one()

                assert remaining == 0, (
                    f"Temporary data remains in {table}"
                )

    print("DATABASE CLEANUP: OK")
    print("MYSQL DISCOVERY INTEGRATION: PASSED")