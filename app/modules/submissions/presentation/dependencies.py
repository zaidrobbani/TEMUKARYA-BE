import os
from pathlib import Path

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_uow
from app.core.unit_of_work import UnitOfWork
from app.modules.notifications.application.use_cases import Notifier
from app.modules.notifications.presentation.dependencies import get_notifier
from app.modules.payments.application.use_cases import FundReleaser
from app.modules.payments.presentation.dependencies import get_fund_releaser
from app.modules.reviews.application.use_cases import ReviewCreator
from app.modules.reviews.presentation.dependencies import get_review_creator
from app.modules.submissions.application.use_cases import (
    ApproveSubmission,
    GetSubmission,
    ListSubmissions,
    OpenSubmissionFile,
    RequestRevision,
    SubmitResult,
)
from app.modules.submissions.domain.repositories import SubmissionFileStorage, SubmissionRepository
from app.modules.submissions.infrastructure.repositories import SqlAlchemySubmissionRepository
from app.modules.submissions.infrastructure.storage import LocalSubmissionFileStorage
from app.modules.workflow.domain.repositories import WorkflowRepository
from app.modules.workflow.presentation.providers import get_workflow_repository


def get_submission_repository(db: Session = Depends(get_db)) -> SubmissionRepository:
    return SqlAlchemySubmissionRepository(db)


def get_submission_storage() -> SubmissionFileStorage:
    root = os.getenv("SUBMISSION_STORAGE_ROOT") or Path.cwd() / "storage" / "submissions"
    return LocalSubmissionFileStorage(root)


def submit_result_use_case(
    workflow: WorkflowRepository = Depends(get_workflow_repository),
    submissions: SubmissionRepository = Depends(get_submission_repository),
    storage: SubmissionFileStorage = Depends(get_submission_storage),
    notifier: Notifier = Depends(get_notifier),
    uow: UnitOfWork = Depends(get_uow),
) -> SubmitResult:
    return SubmitResult(workflow, submissions, storage, notifier, uow)


def list_submissions_use_case(
    workflow: WorkflowRepository = Depends(get_workflow_repository),
    submissions: SubmissionRepository = Depends(get_submission_repository),
) -> ListSubmissions:
    return ListSubmissions(workflow, submissions)


def get_submission_use_case(
    workflow: WorkflowRepository = Depends(get_workflow_repository),
    submissions: SubmissionRepository = Depends(get_submission_repository),
) -> GetSubmission:
    return GetSubmission(workflow, submissions)


def open_submission_file_use_case(
    workflow: WorkflowRepository = Depends(get_workflow_repository),
    submissions: SubmissionRepository = Depends(get_submission_repository),
    storage: SubmissionFileStorage = Depends(get_submission_storage),
) -> OpenSubmissionFile:
    return OpenSubmissionFile(workflow, submissions, storage)


def request_revision_use_case(
    workflow: WorkflowRepository = Depends(get_workflow_repository),
    submissions: SubmissionRepository = Depends(get_submission_repository),
    notifier: Notifier = Depends(get_notifier),
    uow: UnitOfWork = Depends(get_uow),
) -> RequestRevision:
    return RequestRevision(workflow, submissions, notifier, uow)


def approve_submission_use_case(
    workflow: WorkflowRepository = Depends(get_workflow_repository),
    submissions: SubmissionRepository = Depends(get_submission_repository),
    releaser: FundReleaser = Depends(get_fund_releaser),
    reviews: ReviewCreator = Depends(get_review_creator),
    notifier: Notifier = Depends(get_notifier),
    uow: UnitOfWork = Depends(get_uow),
) -> ApproveSubmission:
    return ApproveSubmission(workflow, submissions, releaser, reviews, notifier, uow)
