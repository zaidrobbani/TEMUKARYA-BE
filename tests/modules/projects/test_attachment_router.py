
from datetime import datetime
from io import BytesIO
from uuid import uuid4

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.error_handlers import register_error_handlers
from app.core.exceptions import NotFoundError

from app.modules.users.domain.entities import UserRole

from app.modules.projects.domain.attachments import (
    AttachmentRecord,
)

from app.modules.projects.infrastructure.attachment_storage import (
    AttachmentStorageError,
    InvalidAttachment,
    OversizedAttachment,
    UnsupportedAttachment,
)

from app.modules.projects.presentation.dependencies import (
    AuthenticatedProjectUser,
    get_authenticated_project_user,
)

from app.modules.projects.presentation.attachment_router import (
    get_project_attachment_service,
)

from app.modules.projects.presentation.router import (
    router,
)


# ============================================================
# TEST IDENTIFIERS
# ============================================================

UMKM_ID = "11111111-1111-4111-8111-111111111111"
OTHER_USER_ID = "22222222-2222-4222-8222-222222222222"
PROJECT_ID = "33333333-3333-4333-8333-333333333333"
ATTACHMENT_ID = "44444444-4444-4444-8444-444444444444"

BASE_URL = f"/projects/{PROJECT_ID}/attachments"
FILE_URL = f"{BASE_URL}/{ATTACHMENT_ID}/file"
DELETE_URL = f"{BASE_URL}/{ATTACHMENT_ID}"


# ============================================================
# FAKE APPLICATION SERVICE
# ============================================================

class FakeAttachmentService:
    """
    Fake Service untuk HTTP testing.

    Tidak menggunakan MySQL atau filesystem asli.
    """

    def __init__(self):
        self.items = []
        self.files = {}
        self.calls = []
        self.error_upload = None
        self.project_exists = True

    def _authorize(self, umkm_id, project_id):
        if (
            not self.project_exists
            or umkm_id != UMKM_ID
            or project_id != PROJECT_ID
        ):
            raise NotFoundError(
                "Proyek tidak ditemukan"
            )

    def list(self, umkm_id, project_id):
        self.calls.append("list")

        self._authorize(
            umkm_id,
            project_id,
        )

        return list(self.items)

    def upload(
        self,
        umkm_id,
        project_id,
        filename,
        source,
    ):
        self.calls.append("upload")

        self._authorize(
            umkm_id,
            project_id,
        )

        if self.error_upload is not None:
            raise self.error_upload

        data = source.read()

        attachment = AttachmentRecord(
            id=ATTACHMENT_ID,
            project_id=project_id,
            original_file_name=filename,
            storage_key=f"{uuid4().hex}.pdf",
            mime_type="application/pdf",
            file_size_bytes=len(data),
            uploaded_at=datetime(
                2026, 11, 2, 10, 0
            ),
        )

        self.items.append(attachment)
        self.files[attachment.id] = data

        return attachment

    def file(
        self,
        umkm_id,
        project_id,
        attachment_id,
    ):
        self.calls.append("file")

        self._authorize(
            umkm_id,
            project_id,
        )

        attachment = next(
            (
                item
                for item in self.items
                if item.id == attachment_id
            ),
            None,
        )

        if attachment is None:
            raise NotFoundError(
                "Attachment tidak ditemukan"
            )

        return (
            attachment,
            BytesIO(self.files[attachment_id]),
        )

    def delete(
        self,
        umkm_id,
        project_id,
        attachment_id,
    ):
        self.calls.append("delete")

        self._authorize(
            umkm_id,
            project_id,
        )

        attachment = next(
            (
                item
                for item in self.items
                if item.id == attachment_id
            ),
            None,
        )

        if attachment is None:
            raise NotFoundError(
                "Attachment tidak ditemukan"
            )

        self.items.remove(attachment)
        self.files.pop(attachment_id, None)


# ============================================================
# TEST FIXTURE
# ============================================================

@pytest.fixture
def context():
    app = FastAPI()

    register_error_handlers(app)
    app.include_router(router)

    service = FakeAttachmentService()

    app.dependency_overrides[
        get_project_attachment_service
    ] = lambda: service

    with TestClient(app) as client:
        yield app, client, service

    app.dependency_overrides.clear()


# ============================================================
# TEST AUTHENTICATION HELPER
# ============================================================

def authenticate(
    app,
    role=UserRole.UMKM,
    user_id=UMKM_ID,
):
    app.dependency_overrides[
        get_authenticated_project_user
    ] = lambda: AuthenticatedProjectUser(
        user_id=user_id,
        role=role,
    )


def upload_example(client):
    return client.post(
        BASE_URL,
        files={
            "file": (
                "brief.pdf",
                b"example file content",
                "application/pdf",
            )
        },
    )


# ============================================================
# AUTHENTICATION TESTS
# ============================================================

@pytest.mark.parametrize(
    "method,url",
    [
        ("POST", BASE_URL),
        ("GET", BASE_URL),
        ("GET", FILE_URL),
        ("DELETE", DELETE_URL),
    ],
)
def test_attachment_requires_authentication(
    context,
    method,
    url,
):
    app, client, service = context

    response = client.request(
        method,
        url,
    )

    assert response.status_code == 401
    assert service.calls == []


# ============================================================
# ROLE AUTHORIZATION TESTS
# ============================================================

@pytest.mark.parametrize(
    "method,url",
    [
        ("POST", BASE_URL),
        ("GET", BASE_URL),
        ("GET", FILE_URL),
        ("DELETE", DELETE_URL),
    ],
)
def test_freelancer_cannot_manage_attachments(
    context,
    method,
    url,
):
    app, client, service = context

    authenticate(
        app,
        role=UserRole.FREELANCER,
        user_id=OTHER_USER_ID,
    )

    response = client.request(
        method,
        url,
    )

    assert response.status_code == 403
    assert service.calls == []


# ============================================================
# UPLOAD SUCCESS
# ============================================================

def test_upload_returns_201(context):
    app, client, service = context

    authenticate(app)

    response = upload_example(client)

    assert response.status_code == 201

    body = response.json()

    assert body["id"] == ATTACHMENT_ID
    assert body["project_id"] == PROJECT_ID
    assert body["original_file_name"] == "brief.pdf"
    assert body["mime_type"] == "application/pdf"
    assert body["file_size_bytes"] == len(
        b"example file content"
    )

    # Storage key tidak boleh dibocorkan.
    assert "storage_key" not in body

    assert service.calls == [
        "list",
        "upload",
    ]


# ============================================================
# LIST SUCCESS
# ============================================================

def test_list_returns_200(context):
    app, client, service = context

    authenticate(app)

    upload_example(client)

    service.calls.clear()

    response = client.get(BASE_URL)

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == ATTACHMENT_ID

    assert service.calls == ["list"]


# ============================================================
# DOWNLOAD SUCCESS
# ============================================================

def test_download_returns_private_file(context):
    app, client, service = context

    authenticate(app)

    upload_example(client)

    service.calls.clear()

    response = client.get(FILE_URL)

    assert response.status_code == 200

    assert response.content == b"example file content"

    assert response.headers["content-type"].startswith(
        "application/octet-stream"
    )

    assert response.headers["cache-control"] == (
        "private, no-store"
    )

    assert response.headers[
        "x-content-type-options"
    ] == "nosniff"

    assert "attachment" in response.headers[
        "content-disposition"
    ]

    assert service.calls == ["file"]


# ============================================================
# DELETE SUCCESS
# ============================================================

def test_delete_returns_204(context):
    app, client, service = context

    authenticate(app)

    upload_example(client)

    service.calls.clear()

    response = client.delete(DELETE_URL)

    assert response.status_code == 204
    assert response.content == b""

    assert service.items == []
    assert service.files == {}

    assert service.calls == ["delete"]


# ============================================================
# MISSING ATTACHMENT
# ============================================================

def test_missing_attachment_returns_404(context):
    app, client, service = context

    authenticate(app)

    response = client.get(FILE_URL)

    assert response.status_code == 404


# ============================================================
# FOREIGN OR MISSING PROJECT
# ============================================================

def test_foreign_project_returns_404(context):
    app, client, service = context

    authenticate(
        app,
        user_id=OTHER_USER_ID,
    )

    response = upload_example(client)

    assert response.status_code == 404
    assert "upload" not in service.calls


# ============================================================
# INVALID CONTENT TYPE
# ============================================================

def test_upload_rejects_json(context):
    app, client, service = context

    authenticate(app)

    response = client.post(
        BASE_URL,
        json={"file": "test.pdf"},
    )

    assert response.status_code == 415
    assert "upload" not in service.calls


# ============================================================
# MULTIPLE FILES
# ============================================================

def test_upload_rejects_multiple_files(context):
    app, client, service = context

    authenticate(app)

    response = client.post(
        BASE_URL,
        files=[
            ("file", ("one.pdf", b"first", "application/pdf")),
            ("file", ("two.pdf", b"second", "application/pdf")),
        ],
    )

    assert response.status_code == 422
    assert "upload" not in service.calls


# ============================================================
# OVERSIZED UPLOAD
# ============================================================

def test_upload_rejects_oversized_file(context):
    app, client, service = context

    authenticate(app)

    response = client.post(
        BASE_URL,
        files={
            "file": (
                "large.pdf",
                b"X" * (5 * 1024 * 1024 + 1),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert "upload" not in service.calls


# ============================================================
# INVALID ATTACHMENT ERROR
# ============================================================

def test_invalid_attachment_returns_422(context):
    app, client, service = context

    authenticate(app)

    service.error_upload = InvalidAttachment(
        "File rusak"
    )

    response = upload_example(client)

    assert response.status_code == 422


# ============================================================
# UNSUPPORTED ATTACHMENT ERROR
# ============================================================

def test_unsupported_attachment_returns_415(context):
    app, client, service = context

    authenticate(app)

    service.error_upload = UnsupportedAttachment(
        "Format file tidak didukung"
    )

    response = upload_example(client)

    assert response.status_code == 415


# ============================================================
# STORAGE FAILURE
# ============================================================

def test_storage_failure_returns_503(context):
    app, client, service = context

    authenticate(app)

    service.error_upload = AttachmentStorageError(
        "Storage tidak tersedia"
    )

    response = upload_example(client)

    assert response.status_code == 503

    # Jangan tampilkan detail internal filesystem.
    assert "Storage tidak tersedia" not in (
        response.json()["detail"]
    )