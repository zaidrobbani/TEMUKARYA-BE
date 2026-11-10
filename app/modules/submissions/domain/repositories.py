from abc import ABC, abstractmethod
from typing import BinaryIO

from app.modules.submissions.domain.entities import Submission, SubmissionReview


class SubmissionRepository(ABC):
    @abstractmethod
    def next_version(self, project_id: str) -> int: ...

    @abstractmethod
    def add(self, submission: Submission) -> None:
        """Menyimpan kiriman beserta files-nya."""

    @abstractmethod
    def list_for_project(self, project_id: str) -> list[Submission]:
        """Lengkap dengan files dan review, urut versi terbaru dulu."""

    @abstractmethod
    def get(self, project_id: str, submission_id: str) -> Submission | None: ...

    @abstractmethod
    def latest(self, project_id: str) -> Submission | None: ...

    @abstractmethod
    def add_review(self, review: SubmissionReview) -> None: ...


class SubmissionFileStorage(ABC):
    @abstractmethod
    def save(self, source: BinaryIO, extension: str) -> str:
        """Menyalin isi file dan mengembalikan storage_key."""

    @abstractmethod
    def open(self, storage_key: str) -> BinaryIO: ...

    @abstractmethod
    def delete(self, storage_key: str) -> None: ...
