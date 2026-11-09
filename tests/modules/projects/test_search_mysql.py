import os
from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.database import Base, engine
from app.modules.projects.domain.entities import Project
from app.modules.projects.infrastructure.models import ProjectModel
from app.modules.projects.infrastructure.repositories import (
    SqlAlchemyProjectRepository,
)


# ============================================================
# MYSQL TEST FIXTURE
# ============================================================

@pytest.fixture
def mysql_engine():
    """Gunakan hanya database development lokal."""

    if os.getenv("TEMUKARYA_RUN_MYSQL_TESTS") != "1":
        pytest.skip("MySQL integration tests disabled")

    url = make_url(str(engine.url))

    if url.host not in ("localhost", "127.0.0.1", "db"):
        pytest.skip("Database host is not approved")

    if url.database != "temukarya":
        pytest.skip("Unexpected database name")

    # Reflection sementara untuk FK lintas modul.
    # Bukan solusi metadata permanen aplikasi.
    Base.metadata.reflect(
        bind=engine,
        only=[
            "users",
            "umkm_profiles",
            "skills",
            "project_categories",
        ],
        resolve_fks=True,
    )

    return engine


# ============================================================
# PROJECT FACTORY
# ============================================================

def make_project(
    project_id,
    umkm_id,
    category_id,
    title,
    description,
    budget,
    status,
    published_at,
):
    return Project(
        id=project_id,
        umkm_id=umkm_id,
        category_id=category_id,
        title=title,
        description=description,
        budget=budget,
        deadline=date.today() + timedelta(days=30),
        status=status,
        published_at=published_at,
    )


# ============================================================
# MYSQL MARKETPLACE INTEGRATION TEST
# ============================================================

def test_search_public_projects_mysql(mysql_engine):
    """
    Menguji:
    1. Visibilitas project publik.
    2. Pencarian title dan description.
    3. Filter kategori.
    4. Filter rentang budget.
    5. Pagination.
    6. Pengurutan terbaru.
    7. Escaping karakter pencarian.
    8. Rollback seluruh data test.
    """

    user_id = str(uuid4())

    project_ids = {
        name: str(uuid4())
        for name in (
            "landing",
            "toko",
            "logo",
            "private",
            "started",
            "seo",
        )
    }

    # ========================================================
    # 1. READ EXISTING MASTER DATA
    # ========================================================

    with mysql_engine.connect() as connection:
        categories = connection.execute(
            text("""
                SELECT id
                FROM project_categories
                WHERE is_active = 1
                ORDER BY id
                LIMIT 2
            """)
        ).scalars().all()

    if len(categories) < 2:
        pytest.skip("Minimal dua kategori aktif diperlukan")

    category_a, category_b = categories

    # ========================================================
    # 2. START ISOLATED TRANSACTION
    # ========================================================

    connection = mysql_engine.connect()
    transaction = connection.begin()

    try:
        with Session(bind=connection) as session:
            repository = SqlAlchemyProjectRepository(session)

            # =================================================
            # 3. CREATE TEMPORARY USER + UMKM PROFILE
            # =================================================

            session.execute(
                text("""
                    INSERT INTO users
                        (id, name, email, password_hash, role)
                    VALUES
                        (:id, :name, :email, :password_hash, :role)
                """),
                {
                    "id": user_id,
                    "name": "Marketplace Integration Test",
                    "email": f"market-{user_id}@example.invalid",
                    "password_hash": "test-only",
                    "role": "UMKM",
                },
            )

            session.execute(
                text("""
                    INSERT INTO umkm_profiles
                        (
                            user_id,
                            business_name,
                            business_category,
                            business_address,
                            city
                        )
                    VALUES
                        (
                            :user_id,
                            :business_name,
                            :business_category,
                            :business_address,
                            :city
                        )
                """),
                {
                    "user_id": user_id,
                    "business_name": "Marketplace Test Business",
                    "business_category": "Technology",
                    "business_address": "Temporary Test Address",
                    "city": "Malang",
                },
            )

            assert repository.umkm_profile_exists(user_id)

            # =================================================
            # 4. CREATE SIX TEMPORARY PROJECTS
            # =================================================

            projects = [
                make_project(
                    project_ids["landing"],
                    user_id,
                    category_a,
                    "Website Landing Page",
                    "Membuat halaman promosi produk",
                    1000000,
                    "TERBUKA",
                    datetime(2026, 11, 2, 10, 1),
                ),
                make_project(
                    project_ids["toko"],
                    user_id,
                    category_a,
                    "Website Toko Online",
                    "Membangun toko digital",
                    4000000,
                    "TERBUKA",
                    datetime(2026, 11, 2, 10, 2),
                ),
                make_project(
                    project_ids["logo"],
                    user_id,
                    category_b,
                    "Desain Logo",
                    "Membuat identitas visual merek",
                    2000000,
                    "TERBUKA",
                    datetime(2026, 11, 2, 10, 3),
                ),
                make_project(
                    project_ids["private"],
                    user_id,
                    category_a,
                    "Website Rahasia",
                    "Proyek yang belum dipublikasikan",
                    3000000,
                    "TERBUKA",
                    None,
                ),
                make_project(
                    project_ids["started"],
                    user_id,
                    category_a,
                    "Website Dikerjakan",
                    "Proyek yang sudah berjalan",
                    3000000,
                    "BERJALAN",
                    datetime(2026, 11, 2, 10, 5),
                ),
                make_project(
                    project_ids["seo"],
                    user_id,
                    category_a,
                    "Website SEO",
                    "Optimasi mesin pencari",
                    6000000,
                    "TERBUKA",
                    datetime(2026, 11, 2, 10, 6),
                ),
            ]

            for project in projects:
                repository.add(project)

            session.flush()

            # =================================================
            # 5. PUBLIC VISIBILITY TEST
            # =================================================

            visible = repository.search_public(
                search=None,
                category_id=None,
                min_budget=None,
                max_budget=None,
                limit=20,
                offset=0,
            )

            visible_ids = {project.id for project in visible}

            assert len(visible) == 4

            assert project_ids["private"] not in visible_ids
            assert project_ids["started"] not in visible_ids

            assert project_ids["landing"] in visible_ids
            assert project_ids["toko"] in visible_ids
            assert project_ids["logo"] in visible_ids
            assert project_ids["seo"] in visible_ids

            # =================================================
            # 6. SEARCH TITLE
            # =================================================

            website_results = repository.search_public(
                search="website",
                category_id=None,
                min_budget=None,
                max_budget=None,
                limit=20,
                offset=0,
            )

            website_ids = {
                project.id for project in website_results
            }

            assert website_ids == {
                project_ids["landing"],
                project_ids["toko"],
                project_ids["seo"],
            }

            # =================================================
            # 7. SEARCH DESCRIPTION
            # =================================================

            description_results = repository.search_public(
                search="identitas visual",
                category_id=None,
                min_budget=None,
                max_budget=None,
                limit=20,
                offset=0,
            )

            assert len(description_results) == 1
            assert description_results[0].id == project_ids["logo"]

            # =================================================
            # 8. CATEGORY + BUDGET FILTER
            # =================================================

            filtered = repository.search_public(
                search="website",
                category_id=category_a,
                min_budget=2000000,
                max_budget=5000000,
                limit=20,
                offset=0,
            )

            assert len(filtered) == 1
            assert filtered[0].id == project_ids["toko"]
            assert filtered[0].budget == 4000000

            # =================================================
            # 9. PAGINATION + SORTING
            # =================================================

            first_page = repository.search_public(
                search="website",
                category_id=None,
                min_budget=None,
                max_budget=None,
                limit=2,
                offset=0,
            )

            second_page = repository.search_public(
                search="website",
                category_id=None,
                min_budget=None,
                max_budget=None,
                limit=2,
                offset=2,
            )

            # Published_at descending:
            # SEO -> Toko -> Landing
            assert [
                project.id for project in first_page
            ] == [
                project_ids["seo"],
                project_ids["toko"],
            ]

            assert [
                project.id for project in second_page
            ] == [
                project_ids["landing"],
            ]

            # =================================================
            # 10. SEARCH SPECIAL CHARACTERS
            # =================================================

            wildcard_results = repository.search_public(
                search="%",
                category_id=None,
                min_budget=None,
                max_budget=None,
                limit=20,
                offset=0,
            )

            # % harus diperlakukan sebagai karakter biasa,
            # bukan SQL LIKE wildcard.
            assert wildcard_results == []

    finally:
        # ====================================================
        # 11. ROLLBACK EVEN IF TEST FAILS
        # ====================================================

        transaction.rollback()
        connection.close()

    # ========================================================
    # 12. VERIFY CLEANUP FROM NEW CONNECTION
    # ========================================================

    with mysql_engine.connect() as connection:
        remaining_user = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM users
                WHERE id = :user_id
            """),
            {"user_id": user_id},
        ).scalar_one()

        remaining_profile = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM umkm_profiles
                WHERE user_id = :user_id
            """),
            {"user_id": user_id},
        ).scalar_one()

        remaining_projects = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM projects
                WHERE umkm_id = :user_id
            """),
            {"user_id": user_id},
        ).scalar_one()

        assert remaining_user == 0
        assert remaining_profile == 0
        assert remaining_projects == 0