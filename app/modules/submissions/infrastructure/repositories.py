from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import from_db_utc, to_db_utc
from app.modules.submissions.domain.entities import (
    RevisionItem,
    Submission,
    SubmissionFile,
    SubmissionReview,
)
from app.modules.submissions.domain.repositories import SubmissionRepository
from app.modules.submissions.infrastructure.models import (
    ProjectSubmissionModel,
    SubmissionFileModel,
    SubmissionReviewModel,
)


def _utc(value: datetime | None) -> datetime | None:
    return from_db_utc(value) if value is not None else None


def _review(model: SubmissionReviewModel) -> SubmissionReview:
    return SubmissionReview(
        id=model.id,
        submission_id=model.submission_id,
        reviewer_user_id=model.reviewer_user_id,
        decision=model.decision,
        reviewed_at=_utc(model.reviewed_at),
        review_note=model.review_note,
        focus_areas=tuple(model.focus_areas or ()),
        revision_items=tuple(
            RevisionItem(item.get("title", ""), item.get("detail", ""), item.get("area"))
            for item in (model.revision_items or ())
        ),
    )


def _file(model: SubmissionFileModel) -> SubmissionFile:
    return SubmissionFile(
        id=model.id,
        submission_id=model.submission_id,
        original_file_name=model.original_file_name,
        storage_key=model.storage_key,
        mime_type=model.mime_type,
        file_size_bytes=int(model.file_size_bytes),
        uploaded_at=_utc(model.uploaded_at),
    )


class SqlAlchemySubmissionRepository(SubmissionRepository):
    def __init__(self, session: Session):
        self._session = session

    def next_version(self, project_id: str) -> int:
        current = self._session.scalar(
            select(func.max(ProjectSubmissionModel.version_number)).where(
                ProjectSubmissionModel.project_id == project_id
            )
        )
        return int(current or 0) + 1

    def add(self, submission: Submission) -> None:
        self._session.add(
            ProjectSubmissionModel(
                id=submission.id,
                project_id=submission.project_id,
                version_number=submission.version_number,
                submission_note=submission.submission_note,
                result_url=submission.result_url,
                submitted_at=to_db_utc(submission.submitted_at),
            )
        )
        self._session.flush()
        for file in submission.files:
            self._session.add(
                SubmissionFileModel(
                    id=file.id,
                    submission_id=submission.id,
                    original_file_name=file.original_file_name,
                    storage_key=file.storage_key,
                    mime_type=file.mime_type,
                    file_size_bytes=file.file_size_bytes,
                    uploaded_at=to_db_utc(file.uploaded_at),
                )
            )
        self._session.flush()

    def _hydrate(self, models: list[ProjectSubmissionModel]) -> list[Submission]:
        if not models:
            return []
        ids = [m.id for m in models]
        files: dict[str, list[SubmissionFile]] = {i: [] for i in ids}
        for f in self._session.scalars(
            select(SubmissionFileModel)
            .where(SubmissionFileModel.submission_id.in_(ids))
            .order_by(SubmissionFileModel.uploaded_at, SubmissionFileModel.original_file_name)
        ):
            files[f.submission_id].append(_file(f))
        reviews = {
            r.submission_id: _review(r)
            for r in self._session.scalars(
                select(SubmissionReviewModel)
                .where(SubmissionReviewModel.submission_id.in_(ids))
                .execution_options(populate_existing=True)
            )
        }
        return [
            Submission(
                id=m.id,
                project_id=m.project_id,
                version_number=int(m.version_number),
                submitted_at=_utc(m.submitted_at),
                submission_note=m.submission_note,
                result_url=m.result_url,
                files=tuple(files[m.id]),
                review=reviews.get(m.id),
            )
            for m in models
        ]

    def list_for_project(self, project_id: str) -> list[Submission]:
        models = list(
            self._session.scalars(
                select(ProjectSubmissionModel)
                .where(ProjectSubmissionModel.project_id == project_id)
                .order_by(ProjectSubmissionModel.version_number.desc())
            )
        )
        return self._hydrate(models)

    def get(self, project_id: str, submission_id: str) -> Submission | None:
        model = self._session.scalar(
            select(ProjectSubmissionModel).where(
                ProjectSubmissionModel.id == submission_id, ProjectSubmissionModel.project_id == project_id
            )
        )
        return self._hydrate([model])[0] if model else None

    def latest(self, project_id: str) -> Submission | None:
        model = self._session.scalar(
            select(ProjectSubmissionModel)
            .where(ProjectSubmissionModel.project_id == project_id)
            .order_by(ProjectSubmissionModel.version_number.desc())
            .limit(1)
        )
        return self._hydrate([model])[0] if model else None

    def add_review(self, review: SubmissionReview) -> None:
        self._session.add(
            SubmissionReviewModel(
                id=review.id,
                submission_id=review.submission_id,
                reviewer_user_id=review.reviewer_user_id,
                decision=review.decision,
                review_note=review.review_note,
                reviewed_at=to_db_utc(review.reviewed_at),
                focus_areas=list(review.focus_areas) or None,
                revision_items=[
                    {"title": i.title, "detail": i.detail, "area": i.area} for i in review.revision_items
                ]
                or None,
            )
        )
        self._session.flush()
