
import os
from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.database import Base, engine
from app.modules.projects.domain.entities import Project
from app.modules.projects.infrastructure.models import (
    ProjectModel,
    ProjectSkillModel,
    ProjectAttachmentModel,
)
from app.modules.projects.infrastructure.repositories import (
    SqlAlchemyProjectRepository,
)


@pytest.fixture
def mysql_engine():
    """Aktif hanya untuk integration test lokal."""

    if os.getenv("TEMUKARYA_RUN_MYSQL_TESTS") != "1":
        pytest.skip("MySQL integration tests are not enabled")

    url = make_url(str(engine.url))

    if url.host not in ("localhost", "127.0.0.1", "db"):
        pytest.skip("Database host is not an approved local test host")

    if url.database != "temukarya":
        pytest.skip("Unexpected database name")

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


def test_project_repository_mysql_integration(mysql_engine):
    """Uji repository dengan transaksi MySQL yang di-rollback."""

    user_id = str(uuid4())
    project_id = str(uuid4())

    connection = mysql_engine.connect()
    transaction = connection.begin()

    try:
        with Session(bind=connection) as session:
            repository = SqlAlchemyProjectRepository(session)

            # ----------------------------------------
            # 1. Prepare existing master data
            # ----------------------------------------

            category_id = session.execute(
                text(
                    "SELECT id FROM project_categories "
                    "WHERE is_active = 1 LIMIT 1"
                )
            ).scalar_one()

            skill_id = session.execute(
                text("SELECT id FROM skills LIMIT 1")
            ).scalar_one()

            # ----------------------------------------
            # 2. Create temporary UMKM
            # ----------------------------------------

            session.execute(
                text("""
                    INSERT INTO users
                        (id, name, email, password_hash, role)
                    VALUES
                        (:id, :name, :email, :password_hash, :role)
                """),
                {
                    "id": user_id,
                    "name": "Repository Test User",
                    "email": f"test-{user_id}@example.invalid",
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
                    "business_name": "Test Business",
                    "business_category": "Technology",
                    "business_address": "Test Address",
                    "city": "Malang",
                },
            )

            assert repository.umkm_profile_exists(user_id)
            assert repository.is_active_category(category_id)
            assert skill_id in repository.get_existing_skill_ids(
                [skill_id]
            )

            # ----------------------------------------
            # 3. Create Project
            # ----------------------------------------

            project = Project(
                id=project_id,
                umkm_id=user_id,
                category_id=category_id,
                title="Repository Integration Test",
                description="Temporary project for integration testing.",
                budget=100000,
                deadline=date.today() + timedelta(days=30),
                status="TERBUKA",
                published_at=datetime.now(),
            )

            saved = repository.add(project)

            assert saved.id == project_id
            assert saved.status == "TERBUKA"
            assert saved.budget == 100000

            # ----------------------------------------
            # 4. Save Project Skills
            # ----------------------------------------

            repository.add_skills(project_id, [skill_id])
            session.flush()

            skill_count = session.execute(
                text("""
                    SELECT COUNT(*)
                    FROM project_skills
                    WHERE project_id = :project_id
                """),
                {"project_id": project_id},
            ).scalar_one()

            assert skill_count == 1

            # ----------------------------------------
            # 5. Read Project
            # ----------------------------------------

            loaded = repository.get_by_id(project_id)

            assert loaded is not None
            assert loaded.title == project.title
            assert loaded.umkm_id == user_id

            # ----------------------------------------
            # 6. List Projects by UMKM
            # ----------------------------------------

            projects = repository.list_by_umkm_id(user_id)

            assert any(
                item.id == project_id
                for item in projects
            )

    finally:
        transaction.rollback()
        connection.close()

    # ----------------------------------------
    # 7. Verify Rollback
    # ----------------------------------------

    with mysql_engine.connect() as connection:
        for table, column, identifier in [
            ("users", "id", user_id),
            ("umkm_profiles", "user_id", user_id),
            ("projects", "id", project_id),
            ("project_skills", "project_id", project_id),
        ]:
            remaining = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {table} "
                    f"WHERE {column} = :identifier"
                ),
                {"identifier": identifier},
            ).scalar_one()

            assert remaining == 0


def test_project_repository_mysql_update(mysql_engine):
    """
    Menguji UPDATE project, penggantian skills,
    pengecekan status, dan rollback MySQL.
    """

    from dataclasses import replace

    user_id = str(uuid4())
    project_id = str(uuid4())

    connection = mysql_engine.connect()
    transaction = connection.begin()

    try:
        with Session(bind=connection) as session:
            repository = SqlAlchemyProjectRepository(session)

            # ==================================================
            # 1. PREPARE MASTER DATA
            # ==================================================

            category_id = session.execute(
                text("""
                    SELECT id
                    FROM project_categories
                    WHERE is_active = 1
                    LIMIT 1
                """)
            ).scalar_one()

            skill_ids = session.execute(
                text("""
                    SELECT id
                    FROM skills
                    ORDER BY id
                    LIMIT 2
                """)
            ).scalars().all()

            if len(skill_ids) < 2:
                pytest.skip(
                    "Minimal dua master skills diperlukan"
                )

            old_skill = skill_ids[0]
            new_skill = skill_ids[1]

            # ==================================================
            # 2. CREATE TEMPORARY UMKM
            # ==================================================

            session.execute(
                text("""
                    INSERT INTO users
                        (id, name, email, password_hash, role)
                    VALUES
                        (:id, :name, :email, :password_hash, :role)
                """),
                {
                    "id": user_id,
                    "name": "Update Integration Test",
                    "email": f"update-{user_id}@example.invalid",
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
                    "business_name": "Update Test Business",
                    "business_category": "Technology",
                    "business_address": "Temporary Test Address",
                    "city": "Malang",
                },
            )

            assert repository.umkm_profile_exists(user_id)

            # ==================================================
            # 3. CREATE ORIGINAL PROJECT
            # ==================================================

            original = Project(
                id=project_id,
                umkm_id=user_id,
                category_id=category_id,
                title="Project Sebelum Update",
                description="Deskripsi awal",
                budget=1000000,
                deadline=date.today() + timedelta(days=30),
                status="TERBUKA",
                published_at=datetime.now(),
            )

            repository.add(original)
            repository.add_skills(
                project_id,
                [old_skill],
            )

            session.flush()

            print("\nCREATE ORIGINAL PROJECT: OK")

            # ==================================================
            # 4. UPDATE PROJECT + REPLACE SKILLS
            # ==================================================

            updated = replace(
                original,
                title="Project Setelah Update",
                description="Deskripsi setelah diperbarui",
                budget=5000000,
                deadline=date.today() + timedelta(days=60),
            )

            result = repository.update(
                project=updated,
                skill_ids=(new_skill,),
            )

            assert result is not None
            assert result.id == project_id
            assert result.title == "Project Setelah Update"
            assert result.budget == 5000000

            print("PROJECT UPDATE: OK")

            # ==================================================
            # 5. VERIFY MYSQL VALUES
            # ==================================================

            row = session.execute(
                text("""
                    SELECT title, description, budget
                    FROM projects
                    WHERE id = :project_id
                """),
                {"project_id": project_id},
            ).mappings().one()

            assert row["title"] == "Project Setelah Update"
            assert row["description"] == (
                "Deskripsi setelah diperbarui"
            )
            assert row["budget"] == 5000000

            print("MYSQL PROJECT VALUES: OK")

            # ==================================================
            # 6. VERIFY SKILL REPLACEMENT
            # ==================================================

            saved_skills = set(
                session.execute(
                    text("""
                        SELECT skill_id
                        FROM project_skills
                        WHERE project_id = :project_id
                    """),
                    {"project_id": project_id},
                ).scalars().all()
            )

            assert saved_skills == {new_skill}
            assert old_skill not in saved_skills

            print("PROJECT SKILLS REPLACED: OK")

            # ==================================================
            # 7. VERIFY STATUS PROTECTION
            # ==================================================

            session.execute(
                text("""
                    UPDATE projects
                    SET status = 'BERJALAN'
                    WHERE id = :project_id
                """),
                {"project_id": project_id},
            )

            blocked_update = replace(
                updated,
                title="Perubahan yang Harus Ditolak",
            )

            blocked_result = repository.update(
                project=blocked_update,
                skill_ids=(old_skill,),
            )

            assert blocked_result is None

            actual_title = session.execute(
                text("""
                    SELECT title
                    FROM projects
                    WHERE id = :project_id
                """),
                {"project_id": project_id},
            ).scalar_one()

            assert actual_title == "Project Setelah Update"

            print("STATUS PROTECTION: OK")

    finally:
        transaction.rollback()
        connection.close()

        print("TRANSACTION ROLLBACK: EXECUTED")

    # ======================================================
    # 8. VERIFY DATABASE CLEANUP
    # ======================================================

    with mysql_engine.connect() as connection:
        checks = [
            ("users", "id", user_id),
            ("umkm_profiles", "user_id", user_id),
            ("projects", "id", project_id),
            ("project_skills", "project_id", project_id),
        ]

        for table, column, identifier in checks:
            remaining = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {table} "
                    f"WHERE {column} = :identifier"
                ),
                {"identifier": identifier},
            ).scalar_one()

            assert remaining == 0

    print("DATABASE CLEANUP: OK")
    print("MYSQL UPDATE INTEGRATION: PASSED")


def test_project_repository_mysql_delete(mysql_engine):
    """
    Integration test DELETE Project:
    1. Hapus project yang memenuhi syarat.
    2. Verifikasi ON DELETE CASCADE pada project_skills.
    3. Tolak DELETE project dengan attachment.
    4. Rollback semua data pengujian.
    """

    user_id = str(uuid4())
    deletable_project_id = str(uuid4())
    blocked_project_id = str(uuid4())
    attachment_id = str(uuid4())

    connection = mysql_engine.connect()
    transaction = connection.begin()

    try:
        with Session(bind=connection) as session:
            repository = SqlAlchemyProjectRepository(session)

            # ==================================================
            # 1. PREPARE MASTER DATA
            # ==================================================

            category_id = session.execute(
                text("""
                    SELECT id
                    FROM project_categories
                    WHERE is_active = 1
                    LIMIT 1
                """)
            ).scalar_one()

            skill_id = session.execute(
                text("""
                    SELECT id
                    FROM skills
                    LIMIT 1
                """)
            ).scalar_one()

            # ==================================================
            # 2. CREATE TEMPORARY UMKM
            # ==================================================

            session.execute(
                text("""
                    INSERT INTO users
                        (id, name, email, password_hash, role)
                    VALUES
                        (:id, :name, :email, :password_hash, :role)
                """),
                {
                    "id": user_id,
                    "name": "Delete Integration Test",
                    "email": f"delete-{user_id}@example.invalid",
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
                    "business_name": "Delete Test Business",
                    "business_category": "Technology",
                    "business_address": "Temporary Test Address",
                    "city": "Malang",
                },
            )

            assert repository.umkm_profile_exists(user_id)

            print("\nTEMPORARY UMKM: CREATED")

            # ==================================================
            # 3. CREATE TWO PROJECTS
            # ==================================================

            project_a = Project(
                id=deletable_project_id,
                umkm_id=user_id,
                category_id=category_id,
                title="Project Boleh Dihapus",
                description="Project tanpa data penghalang.",
                budget=1000000,
                deadline=date.today() + timedelta(days=30),
                status="TERBUKA",
                published_at=datetime.now(),
            )

            project_b = Project(
                id=blocked_project_id,
                umkm_id=user_id,
                category_id=category_id,
                title="Project Tidak Boleh Dihapus",
                description="Project memiliki attachment.",
                budget=2000000,
                deadline=date.today() + timedelta(days=30),
                status="TERBUKA",
                published_at=datetime.now(),
            )

            repository.add(project_a)
            repository.add(project_b)

            repository.add_skills(
                deletable_project_id,
                [skill_id],
            )

            session.flush()

            print("TWO PROJECTS: CREATED")

            # ==================================================
            # 4. VERIFY OWNERSHIP PROTECTION
            # ==================================================

            wrong_user_id = str(uuid4())

            unauthorized_delete = repository.delete(
                project_id=deletable_project_id,
                umkm_id=wrong_user_id,
            )

            assert unauthorized_delete is False

            assert repository.get_by_id(
                deletable_project_id
            ) is not None

            print("OWNERSHIP PROTECTION: OK")

            # ==================================================
            # 5. DELETE PROJECT WITHOUT BLOCKERS
            # ==================================================

            deleted = repository.delete(
                project_id=deletable_project_id,
                umkm_id=user_id,
            )

            assert deleted is True

            deleted_project_count = session.execute(
                text("""
                    SELECT COUNT(*)
                    FROM projects
                    WHERE id = :project_id
                """),
                {"project_id": deletable_project_id},
            ).scalar_one()

            assert deleted_project_count == 0

            print("PROJECT DELETE: OK")

            # ==================================================
            # 6. VERIFY ON DELETE CASCADE
            # ==================================================

            remaining_skills = session.execute(
                text("""
                    SELECT COUNT(*)
                    FROM project_skills
                    WHERE project_id = :project_id
                """),
                {"project_id": deletable_project_id},
            ).scalar_one()

            assert remaining_skills == 0

            print("PROJECT SKILLS CASCADE: OK")

            # ==================================================
            # 7. CREATE ATTACHMENT FOR SECOND PROJECT
            # ==================================================

            session.execute(
                text("""
                    INSERT INTO project_attachments
                        (
                            id,
                            project_id,
                            original_file_name,
                            storage_key,
                            mime_type,
                            file_size_bytes
                        )
                    VALUES
                        (
                            :id,
                            :project_id,
                            :original_file_name,
                            :storage_key,
                            :mime_type,
                            :file_size_bytes
                        )
                """),
                {
                    "id": attachment_id,
                    "project_id": blocked_project_id,
                    "original_file_name": "test-document.pdf",
                    "storage_key": (
                        f"integration-tests/{attachment_id}.pdf"
                    ),
                    "mime_type": "application/pdf",
                    "file_size_bytes": 1024,
                },
            )

            print("TEST ATTACHMENT: CREATED")

            # ==================================================
            # 8. VERIFY ATTACHMENT BLOCKS DELETE
            # ==================================================

            blocked = repository.delete(
                project_id=blocked_project_id,
                umkm_id=user_id,
            )

            assert blocked is False

            remaining_project = session.execute(
                text("""
                    SELECT COUNT(*)
                    FROM projects
                    WHERE id = :project_id
                """),
                {"project_id": blocked_project_id},
            ).scalar_one()

            remaining_attachment = session.execute(
                text("""
                    SELECT COUNT(*)
                    FROM project_attachments
                    WHERE id = :attachment_id
                """),
                {"attachment_id": attachment_id},
            ).scalar_one()

            assert remaining_project == 1
            assert remaining_attachment == 1

            print("ATTACHMENT DELETE PROTECTION: OK")

    finally:
        transaction.rollback()
        connection.close()

        print("TRANSACTION ROLLBACK: EXECUTED")

    # ======================================================
    # 9. VERIFY DATABASE CLEANUP
    # ======================================================

    with mysql_engine.connect() as connection:
        checks = [
            ("users", "id", user_id),
            ("umkm_profiles", "user_id", user_id),
            ("projects", "id", deletable_project_id),
            ("projects", "id", blocked_project_id),
            (
                "project_skills",
                "project_id",
                deletable_project_id,
            ),
            (
                "project_attachments",
                "id",
                attachment_id,
            ),
        ]

        for table, column, identifier in checks:
            remaining = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {table} "
                    f"WHERE {column} = :identifier"
                ),
                {"identifier": identifier},
            ).scalar_one()

            assert remaining == 0, (
                f"Data test masih tersisa di {table}"
            )

    print("DATABASE CLEANUP: OK")
    print("MYSQL DELETE INTEGRATION: PASSED")