
import os
from dataclasses import asdict
from datetime import date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine

from app.core.exceptions import NotFoundError

from app.modules.matching.application.dto import (
    RecommendFreelancersInput,
    RecommendProjectsInput,
)

from app.modules.matching.application.use_cases import (
    RecommendFreelancersForProject,
    RecommendProjectsForFreelancer,
)

from app.modules.matching.infrastructure.repositories import (
    SqlAlchemyMatchingRepository,
)


# ============================================================
# MYSQL SAFETY CHECK
# ============================================================

def verify_test_database():
    """
    Mencegah integration test berjalan tanpa sengaja
    pada database production atau host asing.
    """

    if os.getenv("TEMUKARYA_RUN_MYSQL_TESTS") != "1":
        pytest.skip("MySQL integration test disabled")

    if engine.url.get_backend_name() != "mysql":
        pytest.skip("Database bukan MySQL")

    if engine.url.host not in ("localhost", "127.0.0.1"):
        pytest.skip("Hanya database MySQL lokal yang diizinkan")

    if engine.url.database != "temukarya":
        pytest.skip("Nama database harus temukarya")

    if settings.APP_ENV.lower() in ("production", "prod"):
        pytest.skip("Production database tidak diizinkan")


# ============================================================
# INSERT HELPER
# ============================================================

def insert_data(session, sql, rows):
    """
    Melakukan INSERT menggunakan query terparameter.

    Data hanya digunakan pada transaksi test.
    """

    session.execute(text(sql), rows)


# ============================================================
# MYSQL INTEGRATION TEST
# ============================================================

def test_matching_mysql_integration():
    verify_test_database()

    tag = uuid4().hex[:12]

    owner_id = str(uuid4())

    f1 = str(uuid4())
    f2 = str(uuid4())
    f3 = str(uuid4())
    f4 = str(uuid4())

    p1 = str(uuid4())
    p2 = str(uuid4())
    p3 = str(uuid4())
    p4 = str(uuid4())
    p5 = str(uuid4())

    skill_python = f"mt-py-{tag}"
    skill_fastapi = f"mt-api-{tag}"
    skill_mysql = f"mt-my-{tag}"

    category_id = f"mt-cat-{tag}"

    freelancer_ids = {f1, f2, f3, f4}
    project_ids = {p1, p2, p3, p4, p5}

    # Semua perubahan dilakukan dalam satu transaksi.
    connection = engine.connect()
    transaction = connection.begin()

    try:
        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
        ) as session:

            # =================================================
            # 1. VERIFY UUID DATABASE CONTRACT
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

            if id_type.lower() not in ("char", "varchar"):
                pytest.fail(
                    "Kontrak users.id belum menggunakan UUID. "
                    "Sinkronkan migrasi database dengan Zaid."
                )

            print("\nMYSQL UUID CONTRACT: OK")

            # =================================================
            # 2. CREATE TEMPORARY USERS
            # =================================================

            users = [
                (owner_id, "UMKM", "umkm"),
                (f1, "Andi", "freelancer"),
                (f2, "Budi", "freelancer"),
                (f3, "Cici", "freelancer"),
                (f4, "Dina", "freelancer"),
            ]

            insert_data(
                session,
                """
                INSERT INTO users (
                    id, name, email, password_hash, role
                )
                VALUES (
                    :id, :name, :email, :password_hash, :role
                )
                """,
                [
                    {
                        "id": user_id,
                        "name": f"Matching {tag} {name}",
                        "email": (
                            f"matching-{user_id}@example.invalid"
                        ),
                        "password_hash": "test-only-hash",
                        "role": role,
                    }
                    for user_id, name, role in users
                ],
            )

            # =================================================
            # 3. CREATE UMKM PROFILE
            # =================================================

            insert_data(
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
                    "user_id": owner_id,
                    "business_name": f"Test UMKM {tag}",
                    "business_category": "Technology",
                    "business_address": "Test Address",
                    "city": "Malang",
                },
            )

            # =================================================
            # 4. CREATE FREELANCER PROFILES
            # =================================================

            profiles = [
                (f1, "AVAILABLE", "Backend Developer"),
                (f2, "AVAILABLE", "Web Developer"),
                (f3, "AVAILABLE", "Junior Developer"),
                (f4, "BUSY", "Senior Developer"),
            ]

            insert_data(
                session,
                """
                INSERT INTO freelancer_profiles (
                    user_id,
                    professional_title,
                    city,
                    availability_status,
                    service_price_min,
                    service_price_max
                )
                VALUES (
                    :user_id,
                    :title,
                    :city,
                    :availability,
                    :minimum,
                    :maximum
                )
                """,
                [
                    {
                        "user_id": user_id,
                        "title": title,
                        "city": "Malang",
                        "availability": availability,
                        "minimum": 500000,
                        "maximum": 2000000,
                    }
                    for user_id, availability, title in profiles
                ],
            )

            # =================================================
            # 5. CREATE SKILLS
            # =================================================

            insert_data(
                session,
                """
                INSERT INTO skills (id, name)
                VALUES (:id, :name)
                """,
                [
                    {
                        "id": skill_python,
                        "name": f"Matching Python {tag}",
                    },
                    {
                        "id": skill_fastapi,
                        "name": f"Matching FastAPI {tag}",
                    },
                    {
                        "id": skill_mysql,
                        "name": f"Matching MySQL {tag}",
                    },
                ],
            )

            # =================================================
            # 6. CREATE FREELANCER SKILLS
            # =================================================

            freelancer_skills = [
                # Andi: 3/3 = 100%
                (f1, skill_python),
                (f1, skill_fastapi),
                (f1, skill_mysql),

                # Budi: 2/3 = 66.67%
                (f2, skill_python),
                (f2, skill_fastapi),

                # Cici: 1/3 = 33.33%
                (f3, skill_mysql),

                # Dina: 3/3, but BUSY
                (f4, skill_python),
                (f4, skill_fastapi),
                (f4, skill_mysql),
            ]

            insert_data(
                session,
                """
                INSERT INTO freelancer_skills (
                    freelancer_id, skill_id
                )
                VALUES (:freelancer_id, :skill_id)
                """,
                [
                    {
                        "freelancer_id": freelancer_id,
                        "skill_id": skill_id,
                    }
                    for freelancer_id, skill_id
                    in freelancer_skills
                ],
            )

            # =================================================
            # 7. CREATE PROJECT CATEGORY
            # =================================================

            insert_data(
                session,
                """
                INSERT INTO project_categories (
                    id, name, description, is_active
                )
                VALUES (
                    :id, :name, :description, 1
                )
                """,
                {
                    "id": category_id,
                    "name": f"Matching Category {tag}",
                    "description": "Temporary matching category",
                },
            )

            # =================================================
            # 8. CREATE PROJECTS
            # =================================================

            published_at = datetime(2026, 11, 2, 12, 0)

            projects = [
                # Published project, 3 skills
                (p1, "Website UMKM", "TERBUKA", published_at),

                # Published project, 2 skills
                (p2, "Backend API", "TERBUKA", published_at),

                # Not published
                (p3, "Unpublished", "TERBUKA", None),

                # Closed project
                (p4, "Completed", "SELESAI", published_at),

                # Published but no required skills
                (p5, "Empty Skills", "TERBUKA", published_at),
            ]

            insert_data(
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
                    status,
                    published_at
                )
                VALUES (
                    :id,
                    :umkm_id,
                    :category_id,
                    :title,
                    :description,
                    :budget,
                    :deadline,
                    :status,
                    :published_at
                )
                """,
                [
                    {
                        "id": project_id,
                        "umkm_id": owner_id,
                        "category_id": category_id,
                        "title": f"Matching {tag} {title}",
                        "description": "Temporary matching project",
                        "budget": 2000000,
                        "deadline": date(2026, 12, 31),
                        "status": status,
                        "published_at": published,
                    }
                    for (
                        project_id,
                        title,
                        status,
                        published,
                    ) in projects
                ],
            )

            # =================================================
            # 9. CREATE PROJECT SKILLS
            # =================================================

            project_skills = [
                # p1 requires Python + FastAPI + MySQL
                (p1, skill_python),
                (p1, skill_fastapi),
                (p1, skill_mysql),

                # p2 requires Python + MySQL
                (p2, skill_python),
                (p2, skill_mysql),

                # Unpublished and completed
                (p3, skill_python),
                (p4, skill_python),
            ]

            insert_data(
                session,
                """
                INSERT INTO project_skills (
                    project_id, skill_id
                )
                VALUES (:project_id, :skill_id)
                """,
                [
                    {
                        "project_id": project_id,
                        "skill_id": skill_id,
                    }
                    for project_id, skill_id in project_skills
                ],
            )

            print("MYSQL TEST DATA CREATED: OK")

            # =================================================
            # 10. TEST ACTUAL REPOSITORY
            # =================================================

            repository = SqlAlchemyMatchingRepository(
                session=session
            )

            loaded_project = repository.get_project(p1)

            assert loaded_project is not None
            assert loaded_project.umkm_id == owner_id

            assert set(
                loaded_project.required_skill_ids
            ) == {
                skill_python,
                skill_fastapi,
                skill_mysql,
            }

            loaded_freelancer = (
                repository.get_freelancer(f1)
            )

            assert loaded_freelancer is not None

            assert set(
                loaded_freelancer.skill_ids
            ) == {
                skill_python,
                skill_fastapi,
                skill_mysql,
            }

            print("MYSQL PROJECT AND FREELANCER: OK")

            # =================================================
            # 11. CHECK CANDIDATE FILTERING
            # =================================================

            all_available = (
                repository.iter_available_freelancers()
            )

            seeded_available = [
                item
                for item in all_available
                if item.freelancer_id in freelancer_ids
            ]

            assert {
                item.freelancer_id
                for item in seeded_available
            } == {
                f1, f2, f3,
            }

            all_published = (
                repository.iter_published_projects()
            )

            seeded_published = [
                item
                for item in all_published
                if item.project_id in project_ids
            ]

            assert {
                item.project_id
                for item in seeded_published
            } == {
                p1, p2, p5,
            }

            print("MYSQL CANDIDATE FILTERING: OK")

            # =================================================
            # 12. ISOLATE TEST SEED FOR DETERMINISM
            # =================================================

            # Repository SQL sudah diuji di atas.
            # Pembungkus ini hanya membatasi kandidat
            # pada data yang dibuat oleh test ini,
            # sehingga data development milik orang
            # lain tidak mengubah hasil assertion.

            class SeededMatchingRepository:

                def get_project(self, project_id):
                    return repository.get_project(project_id)

                def get_freelancer(self, freelancer_id):
                    return repository.get_freelancer(
                        freelancer_id
                    )

                def iter_available_freelancers(self):
                    return list(seeded_available)

                def iter_published_projects(self):
                    return list(seeded_published)

            seeded_repository = SeededMatchingRepository()

            # =================================================
            # 13. RECOMMEND FREELANCERS FOR UMKM
            # =================================================

            recommend_freelancers = (
                RecommendFreelancersForProject(
                    seeded_repository
                )
            )

            freelancer_page = recommend_freelancers.execute(
                RecommendFreelancersInput(
                    project_id=p1,
                    umkm_id=owner_id,
                )
            )

            assert [
                item.freelancer.freelancer_id
                for item in freelancer_page.items
            ] == [
                f1,
                f2,
            ]

            assert [
                item.match.score_percent
                for item in freelancer_page.items
            ] == [
                100.0,
                66.67,
            ]

            assert all(
                item.match.meets_threshold
                for item in freelancer_page.items
            )

            print("UMKM FREELANCER MATCHING: OK")

            # =================================================
            # 14. VERIFY PROJECT OWNERSHIP
            # =================================================

            with pytest.raises(NotFoundError):
                recommend_freelancers.execute(
                    RecommendFreelancersInput(
                        project_id=p1,
                        umkm_id=str(uuid4()),
                    )
                )

            print("PROJECT OWNERSHIP PROTECTION: OK")

            # =================================================
            # 15. RECOMMEND PROJECTS FOR FREELANCER
            # =================================================

            recommend_projects = (
                RecommendProjectsForFreelancer(
                    seeded_repository
                )
            )

            project_page = recommend_projects.execute(
                RecommendProjectsInput(
                    freelancer_id=f1
                )
            )

            assert [
                item.project.project_id
                for item in project_page.items
            ] == [
                p1,
                p2,
            ]

            assert [
                item.match.score_percent
                for item in project_page.items
            ] == [
                100.0,
                100.0,
            ]

            print("FREELANCER PROJECT MATCHING: OK")

            # =================================================
            # 16. VERIFY PAGINATION
            # =================================================

            first_page = recommend_freelancers.execute(
                RecommendFreelancersInput(
                    project_id=p1,
                    umkm_id=owner_id,
                    limit=1,
                    offset=0,
                )
            )

            assert len(first_page.items) == 1
            assert first_page.has_more is True

            second_page = recommend_freelancers.execute(
                RecommendFreelancersInput(
                    project_id=p1,
                    umkm_id=owner_id,
                    limit=1,
                    offset=1,
                )
            )

            assert len(second_page.items) == 1
            assert second_page.has_more is False

            print("MATCHING PAGINATION: OK")

            # =================================================
            # 17. VERIFY NO SENSITIVE DATA
            # =================================================

            public_data = asdict(
                freelancer_page.items[0]
            )

            assert "password_hash" not in str(
                public_data
            )

            assert "test-only-hash" not in str(
                public_data
            )

            assert "@example.invalid" not in str(
                public_data
            )

            print("SENSITIVE DATA PROTECTION: OK")

    finally:
        # ====================================================
        # 18. ROLLBACK TEMPORARY RECORDS
        # ====================================================

        if transaction.is_active:
            transaction.rollback()

        connection.close()

        print("MYSQL TRANSACTION ROLLBACK: EXECUTED")

    # ========================================================
    # 19. VERIFY DATABASE CLEANUP
    # ========================================================

    checks = [
        (
            "users", "id",
            [owner_id, f1, f2, f3, f4],
        ),
        (
            "umkm_profiles", "user_id",
            [owner_id],
        ),
        (
            "freelancer_profiles", "user_id",
            [f1, f2, f3, f4],
        ),
        (
            "freelancer_skills", "freelancer_id",
            [f1, f2, f3, f4],
        ),
        (
            "skills", "id",
            [skill_python, skill_fastapi, skill_mysql],
        ),
        (
            "project_categories", "id",
            [category_id],
        ),
        (
            "projects", "id",
            [p1, p2, p3, p4, p5],
        ),
        (
            "project_skills", "project_id",
            [p1, p2, p3, p4, p5],
        ),
    ]

    with engine.connect() as check_connection:

        for table, column, ids in checks:

            # Nama tabel/kolom berasal dari
            # konstanta internal, bukan user input.
            statement = text(
                f"SELECT COUNT(*) FROM {table} "
                f"WHERE {column} IN :ids"
            ).bindparams(
                bindparam(
                    "ids",
                    expanding=True,
                )
            )

            remaining = check_connection.execute(
                statement,
                {"ids": ids},
            ).scalar_one()

            assert remaining == 0, (
                f"Temporary data remains in {table}"
            )

    print("DATABASE CLEANUP: OK")
    print("MYSQL MATCHING INTEGRATION: PASSED")