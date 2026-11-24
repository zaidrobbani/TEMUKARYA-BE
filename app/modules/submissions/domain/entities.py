from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_FILES = 10


class ReviewDecision(StrEnum):
    APPROVED = "APPROVED"
    REVISION_REQUESTED = "REVISION_REQUESTED"


REVIEW_DECISION_LABELS = {
    ReviewDecision.APPROVED: "Disetujui",
    ReviewDecision.REVISION_REQUESTED: "Revisi diminta",
}


@dataclass(frozen=True)
class FileType:
    mime_type: str
    signatures: tuple[bytes, ...]
    offset: int = 0


# Sesuai Figma (AI, PSD, PDF, ZIP, PNG) + format umum hasil foto, video, dan tulisan.
ALLOWED_FILE_TYPES: dict[str, FileType] = {
    "pdf": FileType("application/pdf", (b"%PDF-",)),
    "ai": FileType("application/postscript", (b"%PDF-", b"%!PS")),
    "psd": FileType("image/vnd.adobe.photoshop", (b"8BPS",)),
    "zip": FileType("application/zip", (b"PK\x03\x04", b"PK\x05\x06")),
    "png": FileType("image/png", (b"\x89PNG\r\n\x1a\n",)),
    "jpg": FileType("image/jpeg", (b"\xff\xd8\xff",)),
    "jpeg": FileType("image/jpeg", (b"\xff\xd8\xff",)),
    "docx": FileType(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document", (b"PK\x03\x04",)
    ),
    "mp4": FileType("video/mp4", (b"ftyp",), offset=4),
}


def file_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def matches_signature(file_type: FileType, header: bytes) -> bool:
    chunk = header[file_type.offset:]
    return any(chunk.startswith(sig) for sig in file_type.signatures)


def version_label(version_number: int) -> str:
    # Figma: kiriman awal v1.0, revisi berikutnya v1.1, v1.2, ...
    return f"v1.{version_number - 1}"


@dataclass(frozen=True)
class SubmissionFile:
    id: str
    submission_id: str
    original_file_name: str
    storage_key: str
    mime_type: str
    file_size_bytes: int
    uploaded_at: datetime


@dataclass(frozen=True)
class RevisionItem:
    title: str
    detail: str
    area: str | None = None


@dataclass(frozen=True)
class SubmissionReview:
    id: str
    submission_id: str
    reviewer_user_id: str
    decision: str
    reviewed_at: datetime
    review_note: str | None = None
    focus_areas: tuple[str, ...] = ()
    revision_items: tuple[RevisionItem, ...] = ()


@dataclass(frozen=True)
class Submission:
    id: str
    project_id: str
    version_number: int
    submitted_at: datetime
    submission_note: str | None = None
    result_url: str | None = None
    files: tuple[SubmissionFile, ...] = field(default_factory=tuple)
    review: SubmissionReview | None = None

    @property
    def version_label(self) -> str:
        return version_label(self.version_number)
