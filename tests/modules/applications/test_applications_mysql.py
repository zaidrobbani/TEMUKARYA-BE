import os

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.database import engine
from app.core.exceptions import ConflictError, NotFoundError

from app.modules.applications.application.dto import (
    SubmitApplicationInput,
)

from app.modules.applications.application.use_cases import (
    GetMyApplications,
    GetProjectApplicants,
    SubmitApplication,
)

from app.modules.applications.domain.entities import (
    ProjectApplication,
)

from app.modules.applications.infrastructure.repositories import (
    SqlAlchemyApplicationRepository,
)


# ============================================================
# MYSQL TEST CONFIGURATION
# ============================================================

@pytest.fixture
def mysql_engine():
    """
    Integration test hanya dijalankan jika
    diaktifkan secara eksplisit.

    Database yang diizinkan: temukarya lokal.
    """

    if os.getenv("TEMUKARYA_RUN_MYSQL_TESTS") != "1":
        pytest.skip("MySQL integration tests disabled")

    if engine.url.get_backend_name() != "mysql":
        pytest.skip("Database bukan MySQL")

    if engine.url.host not in (
        "localhost",
        "127.0.0.1",
        "db",
    ):
        pytest.skip("Database host tidak diizinkan")

    if engine.url.database != "temukarya":
        pytest.skip("Nama database tidak sesuai")

    return engine


# ============================================================
# TEST UNIT OF WORK
# ============================================================

class FlushOnlyUnitOfWork:
    """
    UnitOfWork khusus integration test.

    commit() diganti flush() agar seluruh data
    tetap berada di transaksi luar yang nantinya
    akan di-rollback.
    """

    def __init__(self, session: Session):
        self.session = session
        self.commit_count = 0

    def commit(self):
        self.session.flush()
        self.commit_count += 1


# ============================================================
# TEST DATA HELPERS
# ============================================================

def create_user(
    session: Session,
    user_id: str,
    role: str,
):
    session.execute(
        text("""
            INSERT INTO users
                (id, name, email, password_hash, role)
            VALUES
                (:id, :name, :email, :password_hash, :role)
        """),
        {
            "id": user_id,
            "name": f"Applications Test {role}",
            "email": f"applications-{user_id}@example.invalid",
            "password_hash": "test-only",
            "role": role,
        },
    )


def create_freelancer_profile(
    session: Session,
    freelancer_id: str,
):
    session.execute(
        text("""
            INSERT INTO freelancer_profiles
                (user_id, professional_title, city)
            VALUES
                (:user_id, :professional_title, :city)
        """),
        {
            "user_id": freelancer_id,
            "professional_title": "Web Developer",
            "city": "Malang",
        },
    )


def create_project(
    session: Session,
    project_id: str,
    umkm_id: str,
    category_id: str,
    status: str = "TERBUKA",
    published: bool = True,
):
    now = datetime.now(timezone.utc).replace(
        tzinfo=None
    )

    session.execute(
        text("""
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
        """),
        {
            "id": project_id,
            "umkm_id": umkm_id,
            "category_id": category_id,
            "title": "MySQL Applications Test Project",
            "description": "Proyek sementara untuk testing",
            "budget": 3000000,
            "deadline": date.today() + timedelta(days=30),
            "status": status,
            "published_at": now if published else None,
        },
    )


def make_application(
    project_id: str,
    freelancer_id: str,
    proposed_price: int = 1500000,
):
    return ProjectApplication(
        id=str(uuid4()),
        project_id=project_id,
        freelancer_id=freelancer_id,
        proposed_price=proposed_price,
        estimated_duration_days=14,
        proposal_message="Saya siap mengerjakan proyek.",
    )


# ============================================================
# MYSQL INTEGRATION TEST
# ============================================================

def test_applications_mysql_integration(mysql_engine):
    """
    Memeriksa:

    1. Profil Freelancer
    2. Status proyek
    3. Kepemilikan UMKM
    4. Submit Application
    5. Metadata MySQL
    6. Lookup Application
    7. Daftar lamaran Freelancer
    8. Daftar pelamar UMKM
    9. Pagination
    10. Unique constraint
    11. Foreign key constraint
    12. Positive-price constraint
    13. Transaction rollback
    """

    umkm_id = str(uuid4())

    freelancer_a = str(uuid4())
    freelancer_b = str(uuid4())

    project_a = str(uuid4())
    project_b = str(uuid4())
    closed_project = str(uuid4())
    draft_project = str(uuid4())

    user_ids = (
        umkm_id,
        freelancer_a,
        freelancer_b,
    )

    project_ids = (
        project_a,
        project_b,
        closed_project,
        draft_project,
    )

    created_application_ids = []

    # ========================================================
    # 1. START ROLLBACK-ONLY TRANSACTION
    # ========================================================

    connection = mysql_engine.connect()
    transaction = connection.begin()

    try:
        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
        ) as session:

            repository = SqlAlchemyApplicationRepository(
                session
            )

            uow = FlushOnlyUnitOfWork(session)

            # =================================================
            # 2. GET EXISTING PROJECT CATEGORY
            # =================================================

            category_id = session.execute(
                text("""
                    SELECT id
                    FROM project_categories
                    WHERE is_active = 1
                    LIMIT 1
                """)
            ).scalar_one()

            # =================================================
            # 3. CREATE TEMPORARY USERS
            # =================================================

            create_user(
                session,
                umkm_id,
                "UMKM",
            )

            create_user(
                session,
                freelancer_a,
                "FREELANCER",
            )

            create_user(
                session,
                freelancer_b,
                "FREELANCER",
            )

            # =================================================
            # 4. CREATE UMKM PROFILE
            # =================================================

            session.execute(
                text("""
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
                """),
                {
                    "user_id": umkm_id,
                    "business_name": "Applications Test UMKM",
                    "business_category": "Technology",
                    "business_address": "Temporary Address",
                    "city": "Malang",
                },
            )

            # =================================================
            # 5. CREATE FREELANCER PROFILES
            # =================================================

            create_freelancer_profile(
                session,
                freelancer_a,
            )

            create_freelancer_profile(
                session,
                freelancer_b,
            )

            assert repository.freelancer_profile_exists(
                freelancer_a
            )

            assert repository.freelancer_profile_exists(
                freelancer_b
            )

            assert not repository.freelancer_profile_exists(
                str(uuid4())
            )

            print("\nFREELANCER PROFILES: OK")

            # =================================================
            # 6. CREATE TEMPORARY PROJECTS
            # =================================================

            create_project(
                session,
                project_a,
                umkm_id,
                category_id,
            )

            create_project(
                session,
                project_b,
                umkm_id,
                category_id,
            )

            create_project(
                session,
                closed_project,
                umkm_id,
                category_id,
                status="BERJALAN",
            )

            create_project(
                session,
                draft_project,
                umkm_id,
                category_id,
                published=False,
            )

            # =================================================
            # 7. PROJECT AVAILABILITY
            # =================================================

            assert repository.project_is_open(
                project_a,
                lock=True,
            )

            assert not repository.project_is_open(
                closed_project
            )

            assert not repository.project_is_open(
                draft_project
            )

            assert not repository.project_is_open(
                str(uuid4())
            )

            print("PROJECT AVAILABILITY: OK")

            # =================================================
            # 8. UMKM OWNERSHIP
            # =================================================

            assert repository.project_owned_by_umkm(
                project_a,
                umkm_id,
            )

            assert not repository.project_owned_by_umkm(
                project_a,
                str(uuid4()),
            )

            print("PROJECT OWNERSHIP: OK")

            # =================================================
            # 9. SUBMIT VIA REAL USE CASE
            # =================================================

            submit = SubmitApplication(
                repository=repository,
                uow=uow,
            )

            saved_a = submit.execute(
                freelancer_id=freelancer_a,
                project_id=project_a,
                data=SubmitApplicationInput(
                    proposed_price=1500000,
                    estimated_duration_days=14,
                    proposal_message=(
                        "Saya dapat membuat website UMKM."
                    ),
                ),
            )

            created_application_ids.append(saved_a.id)

            assert saved_a.status == "SUBMITTED"
            assert saved_a.proposed_price == 1500000
            assert saved_a.submitted_at is not None
            assert uow.commit_count == 1

            print("SUBMIT APPLICATION: OK")

            # =================================================
            # 10. VERIFY MYSQL DATA
            # =================================================

            row = session.execute(
                text("""
                    SELECT
                        project_id,
                        freelancer_id,
                        proposed_price,
                        estimated_duration_days,
                        proposal_message,
                        status
                    FROM project_applications
                    WHERE id = :application_id
                """),
                {
                    "application_id": saved_a.id,
                },
            ).mappings().one()

            assert row["project_id"] == project_a
            assert row["freelancer_id"] == freelancer_a
            assert row["proposed_price"] == 1500000
            assert row["estimated_duration_days"] == 14
            assert row["status"] == "SUBMITTED"

            project_status = session.execute(
                text("""
                    SELECT status
                    FROM projects
                    WHERE id = :project_id
                """),
                {"project_id": project_a},
            ).scalar_one()

            # Submit lamaran tidak boleh mengubah
            # status proyek. Itu milik Workflow Zaid.
            assert project_status == "TERBUKA"

            print("MYSQL METADATA: OK")
            print("PROJECT STATUS UNCHANGED: OK")

            # =================================================
            # 11. CREATE TWO ADDITIONAL APPLICATIONS
            # =================================================

            saved_b = repository.add(
                make_application(
                    project_id=project_a,
                    freelancer_id=freelancer_b,
                )
            )

            saved_c = repository.add(
                make_application(
                    project_id=project_b,
                    freelancer_id=freelancer_a,
                )
            )

            created_application_ids.extend([
                saved_b.id,
                saved_c.id,
            ])

            # =================================================
            # 12. VERIFY APPLICATION LOOKUP
            # =================================================

            found = repository.get_by_id(saved_a.id)

            assert found is not None
            assert found.id == saved_a.id

            by_pair = (
                repository.get_by_project_and_freelancer(
                    project_a,
                    freelancer_a,
                )
            )

            assert by_pair is not None
            assert by_pair.id == saved_a.id

            print("APPLICATION LOOKUP: OK")

            # =================================================
            # 13. FREELANCER APPLICATIONS
            # =================================================

            my_applications = GetMyApplications(
                repository
            )

            page = my_applications.execute(
                freelancer_id=freelancer_a,
                limit=1,
                offset=0,
            )

            assert len(page.items) == 1
            assert page.has_more is True

            all_mine = my_applications.execute(
                freelancer_id=freelancer_a,
                limit=10,
                offset=0,
            )

            assert len(all_mine.items) == 2

            assert all(
                item.freelancer_id == freelancer_a
                for item in all_mine.items
            )

            print("FREELANCER LIST + PAGINATION: OK")

            # =================================================
            # 14. UMKM PROJECT APPLICANTS
            # =================================================

            get_applicants = GetProjectApplicants(
                repository
            )

            applicants = get_applicants.execute(
                umkm_id=umkm_id,
                project_id=project_a,
                limit=10,
                offset=0,
            )

            assert len(applicants.items) == 2

            assert {
                item.freelancer_id
                for item in applicants.items
            } == {
                freelancer_a,
                freelancer_b,
            }

            with pytest.raises(NotFoundError):
                get_applicants.execute(
                    umkm_id=str(uuid4()),
                    project_id=project_a,
                )

            print("UMKM APPLICANTS + OWNERSHIP: OK")

            # =================================================
            # 15. UNIQUE CONSTRAINT
            # =================================================

            # SAVEPOINT membuat IntegrityError bisa
            # diuji tanpa membatalkan semua data
            # yang telah dibuat dalam transaksi luar.
            with pytest.raises(ConflictError):
                with session.begin_nested():
                    repository.add(
                        make_application(
                            project_id=project_a,
                            freelancer_id=freelancer_a,
                        )
                    )

            print("DUPLICATE APPLICATION PROTECTION: OK")

            # =================================================
            # 16. FOREIGN KEY CONSTRAINT
            # =================================================

            with pytest.raises(IntegrityError):
                with session.begin_nested():
                    repository.add(
                        make_application(
                            project_id=str(uuid4()),
                            freelancer_id=freelancer_a,
                        )
                    )

            print("FOREIGN KEY PROTECTION: OK")

            # =================================================
            # 17. POSITIVE PRICE CONSTRAINT
            # =================================================

            with pytest.raises(OperationalError) as exc_info:
                with session.begin_nested():
                    repository.add(
                        make_application(
                            project_id=project_b,
                            freelancer_id=freelancer_b,
                            proposed_price=0,
                        )
                    )

            assert exc_info.value.orig.args[0] == 3819

            print("POSITIVE PRICE CONSTRAINT: OK")

            # =================================================
            # 18. VERIFY DATA AFTER SAVEPOINT ROLLBACKS
            # =================================================

            count = session.execute(
                text("""
                    SELECT COUNT(*)
                    FROM project_applications
                    WHERE project_id IN (
                        :project_a,
                        :project_b
                    )
                """),
                {
                    "project_a": project_a,
                    "project_b": project_b,
                },
            ).scalar_one()

            assert count == 3

            print("TRANSACTION ISOLATION: OK")

    finally:
        # ====================================================
        # 19. ROLLBACK ALL TEMPORARY DATA
        # ====================================================

        transaction.rollback()
        connection.close()

        print("MYSQL TRANSACTION ROLLBACK: EXECUTED")

    # ========================================================
    # 20. VERIFY DATABASE CLEANUP
    # ========================================================

    with mysql_engine.connect() as check_connection:

        checks = [
            ("users", "id", user_ids),
            ("umkm_profiles", "user_id", (umkm_id,)),
            (
                "freelancer_profiles",
                "user_id",
                (freelancer_a, freelancer_b),
            ),
            ("projects", "id", project_ids),
            (
                "project_applications",
                "id",
                tuple(created_application_ids),
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
    print("MYSQL APPLICATIONS INTEGRATION: PASSED")
