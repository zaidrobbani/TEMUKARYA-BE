
import os
from datetime import date, datetime, timedelta
from io import BytesIO
from uuid import uuid4

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import Base, engine, get_db
from app.core.dependencies import get_uow
from app.core.error_handlers import register_error_handlers

from app.modules.users.domain.entities import UserRole

from app.modules.projects.domain.entities import Project

from app.modules.projects.infrastructure.repositories import (
    SqlAlchemyProjectRepository,
)

from app.modules.projects.infrastructure.attachment_repository import (
    SqlAlchemyAttachmentRepository,
)

from app.modules.projects.infrastructure.attachment_storage import (
    LocalProjectAttachmentStorage,
)

from app.modules.projects.presentation.attachment_router import (
    get_project_attachment_storage,
)

from app.modules.projects.presentation.dependencies import (
    AuthenticatedProjectUser,
    get_authenticated_project_user,
)

from app.modules.projects.presentation.router import router


# ============================================================
# MYSQL CONFIGURATION
# ============================================================

@pytest.fixture
def mysql_engine():

    if os.getenv("TEMUKARYA_RUN_MYSQL_TESTS") != "1":
        pytest.skip("MySQL integration test disabled")

    if engine.url.host not in (
        "localhost",
        "127.0.0.1",
        "db",
    ):
        pytest.skip("Database host not approved")

    if engine.url.database != "temukarya":
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


# ============================================================
# ROLLBACK-ONLY UNIT OF WORK
# ============================================================

class FlushOnlyUnitOfWork:
    """
    UoW khusus integration test.

    Tidak melakukan commit permanen.
    Perubahan tetap berada di transaksi luar
    yang akan di-rollback.
    """

    def __init__(self, session):
        self.session = session

    def commit(self):
        self.session.flush()


# ============================================================
# PDF TEST DATA
# ============================================================

def create_valid_pdf() -> bytes:

    writer = PdfWriter()

    writer.add_blank_page(
        width=200,
        height=200,
    )

    output = BytesIO()
    writer.write(output)

    return output.getvalue()


# ============================================================
# END-TO-END MYSQL INTEGRATION
# ============================================================

def test_attachment_http_mysql_storage_flow(
    mysql_engine,
    tmp_path,
):

    user_id = str(uuid4())
    project_id = str(uuid4())

    pdf_content = create_valid_pdf()

    storage = LocalProjectAttachmentStorage(
        tmp_path / "project-attachments"
    )

    connection = mysql_engine.connect()
    transaction = connection.begin()

    try:
        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
        ) as session:

            # ================================================
            # 1. CREATE TEMPORARY UMKM
            # ================================================

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
                        (id, name, email, password_hash, role)
                    VALUES
                        (:id, :name, :email, :password_hash, :role)
                """),
                {
                    "id": user_id,
                    "name": "E2E Attachment Test",
                    "email": f"e2e-{user_id}@example.invalid",
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
                    "business_name": "E2E Test Business",
                    "business_category": "Technology",
                    "business_address": "Temporary Address",
                    "city": "Malang",
                },
            )

            project_repository = (
                SqlAlchemyProjectRepository(session)
            )

            project_repository.add(
                Project(
                    id=project_id,
                    umkm_id=user_id,
                    category_id=category_id,
                    title="Attachment E2E Test",
                    description="Project integration sementara",
                    budget=1000000,
                    deadline=date.today() + timedelta(days=30),
                    status="TERBUKA",
                    published_at=datetime.now(),
                )
            )

            session.flush()

            # ================================================
            # 2. BUILD FASTAPI TEST APPLICATION
            # ================================================

            app = FastAPI()

            register_error_handlers(app)
            app.include_router(router)

            def authenticated_owner():
                return AuthenticatedProjectUser(
                    user_id=user_id,
                    role=UserRole.UMKM,
                )

            app.dependency_overrides[
                get_authenticated_project_user
            ] = authenticated_owner

            app.dependency_overrides[
                get_db
            ] = lambda: session

            app.dependency_overrides[
                get_uow
            ] = lambda: FlushOnlyUnitOfWork(session)

            app.dependency_overrides[
                get_project_attachment_storage
            ] = lambda: storage

            base_url = (
                f"/projects/{project_id}/attachments"
            )

            attachment_repository = (
                SqlAlchemyAttachmentRepository(session)
            )

            with TestClient(app) as client:

                # ============================================
                # 3. INVALID PDF MUST BE REJECTED
                # ============================================

                invalid_response = client.post(
                    base_url,
                    files={
                        "file": (
                            "fake.pdf",
                            b"%PDF-1.4\nFake PDF\n%%EOF",
                            "application/pdf",
                        )
                    },
                )

                assert invalid_response.status_code == 422

                assert list(storage.root.iterdir()) == []

                print("\nINVALID PDF REJECTION: OK")

                # ============================================
                # 4. UPLOAD REAL PDF
                # ============================================

                upload_response = client.post(
                    base_url,
                    files={
                        "file": (
                            "project-brief.pdf",
                            pdf_content,
                            "application/pdf",
                        )
                    },
                )

                assert upload_response.status_code == 201, (
                    upload_response.text
                )

                uploaded = upload_response.json()

                attachment_id = uploaded["id"]

                assert uploaded["project_id"] == project_id
                assert uploaded["original_file_name"] == (
                    "project-brief.pdf"
                )

                assert uploaded["mime_type"] == (
                    "application/pdf"
                )

                assert "storage_key" not in uploaded

                print("HTTP UPLOAD: OK")

                # ============================================
                # 5. VERIFY MYSQL METADATA
                # ============================================

                metadata = attachment_repository.get_by_id(
                    project_id=project_id,
                    attachment_id=attachment_id,
                )

                assert metadata is not None
                assert metadata.file_size_bytes == len(
                    pdf_content
                )

                file_path = (
                    storage.root / metadata.storage_key
                )

                assert file_path.is_file()
                assert file_path.read_bytes() == pdf_content

                print("MYSQL + FILE STORAGE: OK")

                # ============================================
                # 6. HTTP LIST
                # ============================================

                list_response = client.get(
                    base_url
                )

                assert list_response.status_code == 200

                items = list_response.json()

                assert len(items) == 1
                assert items[0]["id"] == attachment_id

                print("HTTP LIST: OK")

                # ============================================
                # 7. HTTP DOWNLOAD
                # ============================================

                file_url = (
                    f"{base_url}/{attachment_id}/file"
                )

                download_response = client.get(
                    file_url
                )

                assert download_response.status_code == 200
                assert download_response.content == pdf_content

                assert download_response.headers[
                    "cache-control"
                ] == "private, no-store"

                assert download_response.headers[
                    "x-content-type-options"
                ] == "nosniff"

                print("HTTP DOWNLOAD: OK")

                # ============================================
                # 8. FOREIGN UMKM ACCESS DENIED
                # ============================================

                app.dependency_overrides[
                    get_authenticated_project_user
                ] = lambda: AuthenticatedProjectUser(
                    user_id=str(uuid4()),
                    role=UserRole.UMKM,
                )

                denied_response = client.get(
                    base_url
                )

                assert denied_response.status_code == 404

                print("FOREIGN UMKM ACCESS: DENIED")

                # Restore authenticated project owner.
                app.dependency_overrides[
                    get_authenticated_project_user
                ] = authenticated_owner

                # ============================================
                # 9. HTTP DELETE
                # ============================================

                delete_response = client.delete(
                    f"{base_url}/{attachment_id}"
                )

                assert delete_response.status_code == 204
                assert delete_response.content == b""

                assert attachment_repository.get_by_id(
                    project_id=project_id,
                    attachment_id=attachment_id,
                ) is None

                assert not file_path.exists()

                print("HTTP DELETE + FILE CLEANUP: OK")

            app.dependency_overrides.clear()

    finally:
        # ====================================================
        # 10. ROLLBACK TEST DATABASE DATA
        # ====================================================

        transaction.rollback()
        connection.close()

    # ========================================================
    # 11. VERIFY DATABASE CLEANUP
    # ========================================================

    with mysql_engine.connect() as check_connection:

        for table, column, identifier in [
            ("users", "id", user_id),
            ("umkm_profiles", "user_id", user_id),
            ("projects", "id", project_id),
        ]:
            count = check_connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {table} "
                    f"WHERE {column} = :identifier"
                ),
                {"identifier": identifier},
            ).scalar_one()

            assert count == 0, (
                f"Temporary data remains in {table}"
            )

    assert list(storage.root.iterdir()) == []

    print("DATABASE ROLLBACK: OK")
    print("FILESYSTEM CLEANUP: OK")
    print("END-TO-END ATTACHMENT TEST: PASSED")