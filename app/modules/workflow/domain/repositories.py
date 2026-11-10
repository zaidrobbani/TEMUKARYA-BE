from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.modules.workflow.domain.entities import (
    Agreement,
    ApplicationSnapshot,
    MyProjectRow,
    Party,
    PaymentSnapshot,
    ProjectParties,
    StatusHistoryEntry,
    SubmissionSnapshot,
    WorkflowProject,
)


class WorkflowRepository(ABC):
    @abstractmethod
    def get_project(self, project_id: str, lock: bool = False) -> WorkflowProject | None:
        """lock=True mengunci baris project (SELECT ... FOR UPDATE) sampai commit."""

    @abstractmethod
    def set_project_status(
        self,
        project_id: str,
        status: str,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None: ...

    @abstractmethod
    def add_history(self, entry: StatusHistoryEntry) -> None: ...

    @abstractmethod
    def list_history(self, project_id: str) -> list[StatusHistoryEntry]:
        """Urut dari yang paling lama."""

    @abstractmethod
    def get_agreement(self, project_id: str, lock: bool = False) -> Agreement | None: ...

    @abstractmethod
    def add_agreement(self, agreement: Agreement) -> None: ...

    @abstractmethod
    def update_agreement(self, agreement: Agreement) -> None: ...

    @abstractmethod
    def get_application(self, application_id: str) -> ApplicationSnapshot | None: ...

    @abstractmethod
    def find_application(self, project_id: str, freelancer_id: str) -> ApplicationSnapshot | None: ...

    @abstractmethod
    def set_application_status(self, application_id: str, status: str) -> None: ...

    @abstractmethod
    def close_submitted_applications(self, project_id: str, status: str) -> list[str]:
        """Ubah semua lamaran SUBMITTED project ini; kembalikan freelancer_id yang terdampak."""

    @abstractmethod
    def is_freelancer(self, user_id: str) -> bool:
        """True bila user punya profil freelancer."""

    @abstractmethod
    def get_parties(self, umkm_id: str, freelancer_id: str | None) -> ProjectParties: ...

    @abstractmethod
    def get_payment(self, agreement_id: str) -> PaymentSnapshot | None: ...

    @abstractmethod
    def latest_submission(self, project_id: str) -> SubmissionSnapshot | None: ...

    @abstractmethod
    def count_revision_requests(self, project_id: str) -> int: ...

    @abstractmethod
    def has_freelancer_review(self, project_id: str) -> bool: ...

    @abstractmethod
    def list_my_projects(
        self, user_id: str, party: Party, status: str | None, limit: int, offset: int
    ) -> list[MyProjectRow]:
        """Urut dari yang terakhir diperbarui."""

    @abstractmethod
    def count_my_projects_by_status(self, user_id: str, party: Party) -> dict[str, int]: ...


class MilestoneWeightReader(Protocol):
    def total_weight(self, project_id: str) -> Decimal: ...


class PaymentPort(Protocol):
    """Disediakan modul payments; workflow tidak menyentuh tabel pembayaran secara langsung."""

    def create_invoice(self, agreement: Agreement, now: datetime) -> None: ...

    def cancel_open_invoice(self, agreement_id: str, now: datetime) -> None: ...
