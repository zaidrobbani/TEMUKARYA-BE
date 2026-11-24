from dataclasses import dataclass
from datetime import date, datetime

from app.modules.workflow.domain.entities import (
    Agreement,
    MyProjectRow,
    Party,
    PaymentSnapshot,
    ProjectParties,
    StatusHistoryEntry,
    SubmissionSnapshot,
    WorkflowAction,
    WorkflowProject,
)


@dataclass(frozen=True)
class Actor:
    user_id: str
    role: str


@dataclass(frozen=True)
class SelectFreelancerInput:
    application_id: str | None = None
    freelancer_id: str | None = None
    scope_of_work: str | None = None


@dataclass(frozen=True)
class UpdateAgreementInput:
    scope_of_work: str | None = None
    agreed_price: int | None = None
    agreed_deadline: date | None = None
    duration_days: int | None = None


@dataclass(frozen=True)
class CancelProjectInput:
    reason: str
    note: str | None = None


@dataclass(frozen=True)
class Cancellation:
    reason: str | None
    note: str | None
    cancelled_by: Party | None
    cancelled_at: datetime


@dataclass(frozen=True)
class WorkflowDetail:
    project: WorkflowProject
    my_party: Party
    parties: ProjectParties
    agreement: Agreement | None
    payment: PaymentSnapshot | None
    latest_submission: SubmissionSnapshot | None
    revision_count: int
    has_review: bool
    history: list[StatusHistoryEntry]
    available_actions: list[WorkflowAction]
    cancellation: Cancellation | None


@dataclass(frozen=True)
class MyProjectsPage:
    items: list[MyProjectRow]
    has_more: bool
    status_counts: dict[str, int]
