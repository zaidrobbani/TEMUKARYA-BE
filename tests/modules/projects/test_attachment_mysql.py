import os

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import Base, engine

from app.modules.projects.domain.attachments import (
    AttachmentRecord,
)

from app.modules.projects.domain.entities import Project

from app.modules.projects.infrastructure.attachment_repository import (
    SqlAlchemyAttachmentRepository,
)

from app.modules.projects.infrastructure.repositories import (
    SqlAlchemyProjectRepository,
)


@pytest.fixture
def mysql_engine():
    if os.getenv("TEMUKARYA_RUN_MYSQL_TESTS") != "1":
        pytest.skip(
            "MySQL integration tests disabled"
        )

    url = engine.url

    if url.host not in (
        "localhost",
        "127.0.0.1",
        "db",
    ):
        pytest.skip(
            "Database host is not approved"
        )

    if url.database != "temukarya":
        pytest.skip(
            "Unexpected database name"
        )

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


def make_project(
    project_id: str,
    umkm_id: str,
    category_id: str,
    status: str = "TERBUKA",
) -> Project:
    return Project(
        id=project_id,
        umkm_id=umkm_id,
        category_id=category_id,
        title="Project Attachment Integration Test",
        description=(
            "Project sementara untuk menguji "
            "metadata attachment."
        ),
        budget=2000000,
        deadline=date.today() + timedelta(days=30),
        status=status,
        published_at=datetime.now(),
    )


def make_attachment(
    project_id: str,
    filename: str,
    extension: str,
    mime_type: str,
) -> AttachmentRecord:
    return AttachmentRecord(
        id=str(uuid4()),
        project_id=project_id,
        original_file_name=filename,
        storage_key=f"{uuid4().hex}.{extension}",
        mime_type=mime_type,
        file_size_bytes=1024,
    )


def test_attachment_repository_mysql(mysql_engine):
    user_id = str(uuid4())
    other_user_id = str(uuid4())

    project_a_id = str(uuid4())
    project_b_id = str(uuid4())

    attachment_a = make_attachment(
        project_id=project_a_id,
        filename="brief-project.pdf",
        extension="pdf",
        mime_type="application/pdf",
    )

    attachment_b = make_attachment(
        project_id=project_a_id,
        filename="referensi-desain.png",
        extension="png",
        mime_type="image/png",
    )

    attachment_c = make_attachment(
        project_id=project_b_id,
        filename="dokumen-lain.pdf",
        extension="pdf",
        mime_type="application/pdf",
    )

    attachment_ids = (
        attachment_a.id,
        attachment_b.id,
        attachment_c.id,
    )

    connection = mysql_engine.connect()
    transaction = connection.begin()

    try:
        with Session(bind=connection) as session:
            project_repository = (
                SqlAlchemyProjectRepository(session)
            )

            attachment_repository = (
                SqlAlchemyAttachmentRepository(session)
            )

            category_id = session.execute(
                text("""
                    SELECT id
                    FROM project_categories
                    WHERE is_active = 1
                    LIMIT 1
                """)
            ).scalar_one()

            session.execute(
                text("""
                    INSERT INTO users
                        (
                            id,
                            name,
                            email,
                            password_hash,
                            role
                        )
                    VALUES
                        (
                            :id,
                            :name,
                            :email,
                            :password_hash,
                            :role
                        )
                """),
                {
                    "id": user_id,
                    "name": "Attachment Integration Test",
                    "email": (
                        f"attachment-{user_id}@example.invalid"
                    ),
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
                    "business_name": "Attachment Test UMKM",
                    "business_category": "Technology",
                    "business_address": "Test Address",
                    "city": "Malang",
                },
            )

            assert project_repository.umkm_profile_exists(
                user_id
            )

            print("\nTEMPORARY UMKM: CREATED")

            project_a = make_project(
                project_id=project_a_id,
                umkm_id=user_id,
                category_id=category_id,
                status="TERBUKA",
            )

            project_b = make_project(
                project_id=project_b_id,
                umkm_id=user_id,
                category_id=category_id,
                status="BERJALAN",
            )

            project_repository.add(project_a)
            project_repository.add(project_b)

            session.flush()

            print("TEMPORARY PROJECTS: CREATED")

            assert attachment_repository.owns_project(
                project_id=project_a_id,
                umkm_id=user_id,
                editable_only=True,
                lock=True,
            ) is True

            assert attachment_repository.owns_project(
                project_id=project_a_id,
                umkm_id=other_user_id,
                editable_only=True,
                lock=True,
            ) is False

            assert attachment_repository.owns_project(
                project_id=str(uuid4()),
                umkm_id=user_id,
                editable_only=True,
                lock=True,
            ) is False

            print("PROJECT OWNERSHIP: OK")

            assert attachment_repository.owns_project(
                project_id=project_a_id,
                umkm_id=user_id,
                editable_only=True,
            ) is True

            assert attachment_repository.owns_project(
                project_id=project_b_id,
                umkm_id=user_id,
                editable_only=False,
            ) is True

            assert attachment_repository.owns_project(
                project_id=project_b_id,
                umkm_id=user_id,
                editable_only=True,
            ) is False

            print("EDITABLE STATUS PROTECTION: OK")

            saved_a = attachment_repository.add(
                attachment_a
            )

            saved_b = attachment_repository.add(
                attachment_b
            )

            saved_c = attachment_repository.add(
                attachment_c
            )

            assert saved_a.id == attachment_a.id
            assert saved_b.id == attachment_b.id
            assert saved_c.id == attachment_c.id

            assert saved_a.project_id == project_a_id
            assert saved_a.storage_key == (
                attachment_a.storage_key
            )

            assert saved_a.mime_type == "application/pdf"
            assert saved_a.file_size_bytes == 1024

            assert isinstance(
                saved_a.uploaded_at,
                datetime,
            )

            print("ATTACHMENT INSERT: OK")

            found = attachment_repository.get_by_id(
                project_id=project_a_id,
                attachment_id=attachment_a.id,
            )

            assert found is not None
            assert found.id == attachment_a.id
            assert found.original_file_name == (
                "brief-project.pdf"
            )

            missing = attachment_repository.get_by_id(
                project_id=project_a_id,
                attachment_id=str(uuid4()),
            )

            assert missing is None

            print("ATTACHMENT GET BY ID: OK")

            cross_project = (
                attachment_repository.get_by_id(
                    project_id=project_a_id,
                    attachment_id=attachment_c.id,
                )
            )

            assert cross_project is None

            print("ATTACHMENT PROJECT ISOLATION: OK")

            list_a = (
                attachment_repository.list_by_project(
                    project_id=project_a_id,
                    lock=True,
                )
            )

            list_b = (
                attachment_repository.list_by_project(
                    project_id=project_b_id,
                )
            )

            assert {
                attachment.id
                for attachment in list_a
            } == {
                attachment_a.id,
                attachment_b.id,
            }

            assert [
                attachment.id
                for attachment in list_b
            ] == [
                attachment_c.id,
            ]

            print("ATTACHMENT LIST: OK")

            wrong_project_delete = (
                attachment_repository.delete(
                    project_id=project_a_id,
                    attachment_id=attachment_c.id,
                )
            )

            assert wrong_project_delete is False

            assert attachment_repository.get_by_id(
                project_id=project_b_id,
                attachment_id=attachment_c.id,
            ) is not None

            print("CROSS-PROJECT DELETE PROTECTION: OK")

            deleted = attachment_repository.delete(
                project_id=project_a_id,
                attachment_id=attachment_a.id,
            )

            assert deleted is True

            assert attachment_repository.get_by_id(
                project_id=project_a_id,
                attachment_id=attachment_a.id,
            ) is None

            remaining_a = (
                attachment_repository.list_by_project(
                    project_id=project_a_id,
                )
            )

            assert [
                attachment.id
                for attachment in remaining_a
            ] == [
                attachment_b.id,
            ]

            print("ATTACHMENT DELETE: OK")

            remaining_count = session.execute(
                text("""
                    SELECT COUNT(*)
                    FROM project_attachments
                    WHERE project_id IN (
                        :project_a_id,
                        :project_b_id
                    )
                """),
                {
                    "project_a_id": project_a_id,
                    "project_b_id": project_b_id,
                },
            ).scalar_one()

            assert remaining_count == 2

            print("MYSQL ATTACHMENT VALUES: OK")

    finally:
        transaction.rollback()
        connection.close()

        print("TRANSACTION ROLLBACK: EXECUTED")

    with mysql_engine.connect() as connection:
        user_count = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM users
                WHERE id = :user_id
            """),
            {"user_id": user_id},
        ).scalar_one()

        profile_count = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM umkm_profiles
                WHERE user_id = :user_id
            """),
            {"user_id": user_id},
        ).scalar_one()

        project_count = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM projects
                WHERE id IN (
                    :project_a_id,
                    :project_b_id
                )
            """),
            {
                "project_a_id": project_a_id,
                "project_b_id": project_b_id,
            },
        ).scalar_one()

        attachment_count = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM project_attachments
                WHERE id IN (
                    :attachment_a,
                    :attachment_b,
                    :attachment_c
                )
            """),
            {
                "attachment_a": attachment_ids[0],
                "attachment_b": attachment_ids[1],
                "attachment_c": attachment_ids[2],
            },
        ).scalar_one()

        assert user_count == 0
        assert profile_count == 0
        assert project_count == 0
        assert attachment_count == 0

    print("DATABASE CLEANUP: OK")
    print("MYSQL ATTACHMENT REPOSITORY: PASSED")
