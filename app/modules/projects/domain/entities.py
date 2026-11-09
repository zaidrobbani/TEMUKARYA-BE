from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Project:
    id: str
    umkm_id: str
    category_id: str
    title: str
    description: str
    budget: int
    deadline: date
    status: str
    published_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class ProjectSkill:
    project_id: str
    skill_id: str


@dataclass(frozen=True)
class ProjectAttachment:
    id: str
    project_id: str
    original_file_name: str
    storage_key: str
    mime_type: str
    file_size_bytes: int
    uploaded_at: datetime | None = None