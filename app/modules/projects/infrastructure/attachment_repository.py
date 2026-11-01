
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.projects.domain.attachments import (
    AttachmentRecord,
    AttachmentRepository,
)
from app.modules.projects.infrastructure.models import (
    ProjectAttachmentModel,
    ProjectModel,
)


class SqlAlchemyAttachmentRepository(AttachmentRepository):
    """
    Repository metadata attachment.

    Tidak melakukan commit.
    Transaction boundary dikelola oleh UnitOfWork.
    """

    def __init__(self, session: Session):
        self._session = session

    # ========================================================
    # PROJECT OWNERSHIP
    # ========================================================

    def owns_project(
        self,
        project_id: str,
        umkm_id: str,
        editable_only: bool = False,
        lock: bool = False,
    ) -> bool:
        """
        Pastikan project dimiliki UMKM terkait.

        editable_only=True membatasi akses tulis
        pada project yang masih TERBUKA dan
        belum dimulai.

        lock=True menggunakan SELECT FOR UPDATE
        untuk mengunci parent project saat
        transaksi perubahan attachment.
        """

        statement = select(ProjectModel.id).where(
            ProjectModel.id == project_id,
            ProjectModel.umkm_id == umkm_id,
        )

        if editable_only:
            statement = statement.where(
                ProjectModel.status == "TERBUKA",
                ProjectModel.started_at.is_(None),
            )

        if lock:
            statement = statement.with_for_update()

        result = self._session.scalar(statement)

        return result is not None

    # ========================================================
    # LIST ATTACHMENTS
    # ========================================================

    def list_by_project(
        self,
        project_id: str,
        lock: bool = False,
    ) -> list[AttachmentRecord]:
        """Mengambil attachment berdasarkan project ID."""

        statement = (
            select(ProjectAttachmentModel)
            .where(
                ProjectAttachmentModel.project_id == project_id
            )
            .order_by(
                ProjectAttachmentModel.uploaded_at.asc(),
                ProjectAttachmentModel.id.asc(),
            )
        )

        if lock:
            statement = statement.with_for_update()

        models = self._session.scalars(
            statement
        ).all()

        return [
            _to_attachment_record(model)
            for model in models
        ]

    # ========================================================
    # GET ATTACHMENT
    # ========================================================

    def get_by_id(
        self,
        project_id: str,
        attachment_id: str,
    ) -> AttachmentRecord | None:
        """
        Ambil attachment yang benar-benar
        terhubung dengan project terkait.
        """

        statement = select(ProjectAttachmentModel).where(
            ProjectAttachmentModel.id == attachment_id,
            ProjectAttachmentModel.project_id == project_id,
        )

        model = self._session.scalar(statement)

        if model is None:
            return None

        return _to_attachment_record(model)

    # ========================================================
    # ADD ATTACHMENT
    # ========================================================

    def add(
        self,
        attachment: AttachmentRecord,
    ) -> AttachmentRecord:
        """Menyimpan metadata file ke database."""

        model = ProjectAttachmentModel(
            id=attachment.id,
            project_id=attachment.project_id,
            original_file_name=attachment.original_file_name,
            storage_key=attachment.storage_key,
            mime_type=attachment.mime_type,
            file_size_bytes=attachment.file_size_bytes,
        )

        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)

        return _to_attachment_record(model)

    # ========================================================
    # DELETE ATTACHMENT METADATA
    # ========================================================

    def delete(
        self,
        project_id: str,
        attachment_id: str,
    ) -> bool:
        """
        Menghapus metadata attachment dari database.

        File fisik TIDAK dihapus di sini.

        Pemanggil harus melakukan commit database
        sebelum membersihkan file fisik.
        """

        statement = delete(
            ProjectAttachmentModel
        ).where(
            ProjectAttachmentModel.id == attachment_id,
            ProjectAttachmentModel.project_id == project_id,
        )

        result = self._session.execute(
            statement
        )

        return result.rowcount == 1


# ============================================================
# MAPPER: SQLALCHEMY MODEL -> DOMAIN RECORD
# ============================================================

def _to_attachment_record(
    model: ProjectAttachmentModel,
) -> AttachmentRecord:
    """Mengubah ORM Model ke domain record."""

    return AttachmentRecord(
        id=model.id,
        project_id=model.project_id,
        original_file_name=model.original_file_name,
        storage_key=model.storage_key,
        mime_type=model.mime_type,
        file_size_bytes=model.file_size_bytes,
        uploaded_at=model.uploaded_at,
    )