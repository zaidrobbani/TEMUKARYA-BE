from sqlalchemy import delete, select, text
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
    def __init__(self, session: Session):
        self._session = session

    def owns_project(
        self,
        project_id: str,
        umkm_id: str,
        editable_only: bool = False,
        lock: bool = False,
    ) -> bool:
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

    def freelancer_can_view(
        self,
        project_id: str,
        freelancer_id: str,
    ) -> bool:
        row = self._session.execute(
            text(
                "SELECT 1 FROM projects p "
                "LEFT JOIN project_agreements a ON a.project_id = p.id "
                "WHERE p.id = :pid AND ("
                "(p.status = 'TERBUKA' AND p.published_at IS NOT NULL) "
                "OR a.freelancer_id = :fid) LIMIT 1"
            ),
            {"pid": project_id, "fid": freelancer_id},
        ).first()
        return row is not None

    def list_by_project(
        self,
        project_id: str,
        lock: bool = False,
    ) -> list[AttachmentRecord]:
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

    def get_by_id(
        self,
        project_id: str,
        attachment_id: str,
    ) -> AttachmentRecord | None:
        statement = select(ProjectAttachmentModel).where(
            ProjectAttachmentModel.id == attachment_id,
            ProjectAttachmentModel.project_id == project_id,
        )

        model = self._session.scalar(statement)

        if model is None:
            return None

        return _to_attachment_record(model)

    def add(
        self,
        attachment: AttachmentRecord,
    ) -> AttachmentRecord:
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

    def delete(
        self,
        project_id: str,
        attachment_id: str,
    ) -> bool:
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


def _to_attachment_record(
    model: ProjectAttachmentModel,
) -> AttachmentRecord:
    return AttachmentRecord(
        id=model.id,
        project_id=model.project_id,
        original_file_name=model.original_file_name,
        storage_key=model.storage_key,
        mime_type=model.mime_type,
        file_size_bytes=model.file_size_bytes,
        uploaded_at=model.uploaded_at,
    )
