
from datetime import datetime
from io import BytesIO
from uuid import uuid4

import pytest

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)

from app.modules.projects.application.attachment_service import (
    MAX_PROJECT_ATTACHMENTS,
    ProjectAttachmentService,
)

from app.modules.projects.domain.attachments import (
    AttachmentRecord,
)

from app.modules.projects.infrastructure.attachment_storage import (
    AttachmentStorageError,
    StoredAttachment,
)


UMKM_ID = "11111111-1111-4111-8111-111111111111"
OTHER_UMKM_ID = "22222222-2222-4222-8222-222222222222"
PROJECT_ID = "33333333-3333-4333-8333-333333333333"


# ============================================================
# TEST DATA FACTORY
# ============================================================

def make_attachment(
    attachment_id=None,
    storage_key=None,
):
    return AttachmentRecord(
        id=attachment_id or str(uuid4()),
        project_id=PROJECT_ID,
        original_file_name="brief.pdf",
        storage_key=storage_key or f"{uuid4().hex}.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        uploaded_at=datetime(2026, 11, 2, 10, 0),
    )


# ============================================================
# FAKE REPOSITORY
# ============================================================

class FakeAttachmentRepository:

    def __init__(self):
        self.items = []
        self.owner_id = UMKM_ID
        self.editable = True
        self.project_exists = True
        self.fail_add = False
        self.authorization_calls = []

    def owns_project(
        self,
        project_id,
        umkm_id,
        editable_only=False,
        lock=False,
    ):
        self.authorization_calls.append(
            (project_id, umkm_id, editable_only, lock)
        )

        if not self.project_exists:
            return False

        if project_id != PROJECT_ID:
            return False

        if umkm_id != self.owner_id:
            return False

        if editable_only and not self.editable:
            return False

        return True

    def list_by_project(
        self,
        project_id,
        lock=False,
    ):
        return [
            item
            for item in self.items
            if item.project_id == project_id
        ]

    def get_by_id(
        self,
        project_id,
        attachment_id,
    ):
        return next(
            (
                item
                for item in self.items
                if item.project_id == project_id
                and item.id == attachment_id
            ),
            None,
        )

    def add(self, attachment):
        if self.fail_add:
            raise RuntimeError(
                "Simulated database insert failure"
            )

        saved = AttachmentRecord(
            id=attachment.id,
            project_id=attachment.project_id,
            original_file_name=attachment.original_file_name,
            storage_key=attachment.storage_key,
            mime_type=attachment.mime_type,
            file_size_bytes=attachment.file_size_bytes,
            uploaded_at=datetime(2026, 11, 2, 10, 0),
        )

        self.items.append(saved)

        return saved

    def delete(
        self,
        project_id,
        attachment_id,
    ):
        target = self.get_by_id(
            project_id,
            attachment_id,
        )

        if target is None:
            return False

        self.items.remove(target)

        return True


# ============================================================
# FAKE STORAGE
# ============================================================

class FakeAttachmentStorage:

    def __init__(self):
        self.files = {}
        self.deleted_keys = []
        self.save_count = 0
        self.fail_save = False
        self.fail_delete = False

    def save(self, source):
        if self.fail_save:
            raise AttachmentStorageError(
                "Simulated storage failure"
            )

        data = source.read()

        self.save_count += 1

        storage_key = f"{uuid4().hex}.pdf"

        self.files[storage_key] = data

        return StoredAttachment(
            storage_key=storage_key,
            mime_type="application/pdf",
            file_size_bytes=len(data),
        )

    def open(self, storage_key):
        if storage_key not in self.files:
            raise AttachmentStorageError(
                "File not found"
            )

        return BytesIO(
            self.files[storage_key]
        )

    def delete(self, storage_key):
        if self.fail_delete:
            raise AttachmentStorageError(
                "Simulated file cleanup failure"
            )

        self.deleted_keys.append(storage_key)
        self.files.pop(storage_key, None)


# ============================================================
# FAKE UNIT OF WORK
# ============================================================

class FakeUnitOfWork:

    def __init__(self):
        self.commit_count = 0
        self.fail_commit = False

    def commit(self):
        self.commit_count += 1

        if self.fail_commit:
            raise RuntimeError(
                "Simulated commit failure"
            )


# ============================================================
# TEST FIXTURE
# ============================================================

@pytest.fixture
def context():

    repository = FakeAttachmentRepository()
    storage = FakeAttachmentStorage()
    uow = FakeUnitOfWork()

    service = ProjectAttachmentService(
        repository=repository,
        storage=storage,
        uow=uow,
    )

    return service, repository, storage, uow


def upload_file(
    service,
    filename="brief.pdf",
):
    return service.upload(
        umkm_id=UMKM_ID,
        project_id=PROJECT_ID,
        filename=filename,
        source=BytesIO(b"test document bytes"),
    )


# ============================================================
# UPLOAD TESTS
# ============================================================

def test_upload_success(context):
    service, repository, storage, uow = context

    result = upload_file(
        service,
        filename="C:\\Users\\Test\\brief.pdf",
    )

    assert result.project_id == PROJECT_ID
    assert result.original_file_name == "brief.pdf"
    assert result.mime_type == "application/pdf"
    assert result.file_size_bytes == len(
        b"test document bytes"
    )

    assert result.storage_key in storage.files
    assert len(repository.items) == 1
    assert uow.commit_count == 1

    assert repository.authorization_calls[0] == (
        PROJECT_ID,
        UMKM_ID,
        True,
        True,
    )


def test_other_umkm_cannot_upload(context):
    service, repository, storage, uow = context

    with pytest.raises(NotFoundError):
        service.upload(
            umkm_id=OTHER_UMKM_ID,
            project_id=PROJECT_ID,
            filename="brief.pdf",
            source=BytesIO(b"test"),
        )

    assert storage.save_count == 0
    assert uow.commit_count == 0


def test_noneditable_project_cannot_upload(context):
    service, repository, storage, uow = context

    repository.editable = False

    with pytest.raises(NotFoundError):
        upload_file(service)

    assert storage.save_count == 0
    assert uow.commit_count == 0


def test_upload_limit_five_attachments(context):
    service, repository, storage, uow = context

    repository.items = [
        make_attachment()
        for _ in range(MAX_PROJECT_ATTACHMENTS)
    ]

    with pytest.raises(ConflictError):
        upload_file(service)

    assert storage.save_count == 0
    assert uow.commit_count == 0


@pytest.mark.parametrize(
    "filename",
    [
        "",
        "../",
        "evil\n.pdf",
        "x" * 256,
    ],
)
def test_upload_invalid_filename(context, filename):
    service, repository, storage, uow = context

    with pytest.raises(BadRequestError):
        upload_file(
            service,
            filename=filename,
        )

    assert storage.save_count == 0
    assert uow.commit_count == 0


def test_upload_storage_failure(context):
    service, repository, storage, uow = context

    storage.fail_save = True

    with pytest.raises(AttachmentStorageError):
        upload_file(service)

    assert repository.items == []
    assert uow.commit_count == 0


def test_upload_database_failure_removes_file(context):
    service, repository, storage, uow = context

    repository.fail_add = True

    with pytest.raises(RuntimeError):
        upload_file(service)

    assert repository.items == []
    assert storage.files == {}
    assert len(storage.deleted_keys) == 1
    assert uow.commit_count == 0


def test_upload_commit_failure_removes_file(context):
    service, repository, storage, uow = context

    uow.fail_commit = True

    with pytest.raises(RuntimeError):
        upload_file(service)

    # Fake Repository belum memiliki rollback database.
    # Kita hanya membuktikan cleanup file dipanggil.
    assert storage.files == {}
    assert len(storage.deleted_keys) == 1
    assert uow.commit_count == 1


def test_upload_cleanup_failure_is_reported(context):
    service, repository, storage, uow = context

    repository.fail_add = True
    storage.fail_delete = True

    with pytest.raises(AttachmentStorageError):
        upload_file(service)

    # File yatim masih ada dan harus ditangani.
    assert len(storage.files) == 1
    assert uow.commit_count == 0


# ============================================================
# LIST & DOWNLOAD TESTS
# ============================================================

def test_owner_can_list_attachments(context):
    service, repository, storage, uow = context

    repository.items = [
        make_attachment(),
        make_attachment(),
    ]

    result = service.list(
        umkm_id=UMKM_ID,
        project_id=PROJECT_ID,
    )

    assert len(result) == 2
    assert uow.commit_count == 0


def test_other_umkm_cannot_list_attachments(context):
    service, repository, storage, uow = context

    repository.items = [
        make_attachment(),
    ]

    with pytest.raises(NotFoundError):
        service.list(
            umkm_id=OTHER_UMKM_ID,
            project_id=PROJECT_ID,
        )


def test_owner_can_read_attachment(context):
    service, repository, storage, uow = context

    saved = upload_file(service)

    attachment, stream = service.file(
        umkm_id=UMKM_ID,
        project_id=PROJECT_ID,
        attachment_id=saved.id,
    )

    with stream:
        content = stream.read()

    assert attachment.id == saved.id
    assert content == b"test document bytes"


def test_missing_attachment_cannot_be_read(context):
    service, repository, storage, uow = context

    with pytest.raises(NotFoundError):
        service.file(
            umkm_id=UMKM_ID,
            project_id=PROJECT_ID,
            attachment_id=str(uuid4()),
        )


# ============================================================
# DELETE TESTS
# ============================================================

def test_delete_success(context):
    service, repository, storage, uow = context

    saved = upload_file(service)

    assert saved.storage_key in storage.files

    service.delete(
        umkm_id=UMKM_ID,
        project_id=PROJECT_ID,
        attachment_id=saved.id,
    )

    assert repository.items == []
    assert saved.storage_key not in storage.files

    # Satu commit upload dan satu commit delete.
    assert uow.commit_count == 2


def test_other_umkm_cannot_delete_attachment(context):
    service, repository, storage, uow = context

    saved = upload_file(service)

    with pytest.raises(NotFoundError):
        service.delete(
            umkm_id=OTHER_UMKM_ID,
            project_id=PROJECT_ID,
            attachment_id=saved.id,
        )

    assert saved.storage_key in storage.files
    assert len(repository.items) == 1
    assert uow.commit_count == 1


def test_missing_attachment_cannot_be_deleted(context):
    service, repository, storage, uow = context

    with pytest.raises(NotFoundError):
        service.delete(
            umkm_id=UMKM_ID,
            project_id=PROJECT_ID,
            attachment_id=str(uuid4()),
        )

    assert uow.commit_count == 0


def test_delete_commit_failure_keeps_file(context):
    service, repository, storage, uow = context

    saved = upload_file(service)

    uow.fail_commit = True

    with pytest.raises(RuntimeError):
        service.delete(
            umkm_id=UMKM_ID,
            project_id=PROJECT_ID,
            attachment_id=saved.id,
        )

    # File fisik tidak boleh dihapus sebelum commit.
    assert saved.storage_key in storage.files


def test_delete_storage_failure_is_reported(context):
    service, repository, storage, uow = context

    saved = upload_file(service)

    storage.fail_delete = True

    with pytest.raises(AttachmentStorageError):
        service.delete(
            umkm_id=UMKM_ID,
            project_id=PROJECT_ID,
            attachment_id=saved.id,
        )

    # Metadata telah terhapus setelah commit.
    assert repository.items == []

    # File yatim masih ada karena cleanup gagal.
    assert saved.storage_key in storage.files

    assert uow.commit_count == 2