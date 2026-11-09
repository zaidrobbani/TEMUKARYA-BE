
from dataclasses import dataclass

from app.modules.applications.domain.entities import (
    ProjectApplication,
)


@dataclass(frozen=True)
class SubmitApplicationInput:
    """
    Data yang dikirim Freelancer saat melamar.

    freelancer_id tidak dimasukkan di sini.
    Identitas Freelancer nantinya berasal
    dari autentikasi JWT, bukan request body.
    """

    proposed_price: int
    estimated_duration_days: int
    proposal_message: str


@dataclass(frozen=True)
class ApplicationsPage:
    """
    Hasil daftar lamaran dengan pagination.
    """

    items: tuple[ProjectApplication, ...]
    limit: int
    offset: int
    has_more: bool