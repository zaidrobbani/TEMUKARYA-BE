
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class AttachmentRecord:
    """Metadata attachment yang tersimpan di database."""

    id: str
    project_id: str
    original_file_name: str
    storage_key: str
    mime_type: str
    file_size_bytes: int
    uploaded_at: datetime | None = None


class AttachmentRepository(Protocol):
    """Kontrak akses metadata attachment proyek."""

    def owns_project(
        self,
        project_id: str,
        umkm_id: str,
        editable_only: bool = False,
        lock: bool = False,
    ) -> bool:
        ...

    def list_by_project(
        self,
        project_id: str,
        lock: bool = False,
    ) -> list[AttachmentRecord]:
        ...

    def get_by_id(
        self,
        project_id: str,
        attachment_id: str,
    ) -> AttachmentRecord | None:
        ...

    def add(
        self,
        attachment: AttachmentRecord,
    ) -> AttachmentRecord:
        ...

    def delete(
        self,
        project_id: str,
        attachment_id: str,
    ) -> bool:
        ...