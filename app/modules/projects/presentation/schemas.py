from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.core.responses import UtcDateTime


# ============================================================
# CREATE PROJECT REQUEST

class CreateProjectRequest(BaseModel):
    """Schema request pembuatan proyek oleh UMKM."""

    model_config = ConfigDict(extra="forbid")

    category_id: str = Field(
        min_length=1,
        max_length=50,
    )

    title: str = Field(
        min_length=1,
        max_length=180,
    )

    description: str = Field(
        min_length=1,
    )

    budget: int = Field(
        gt=0,
    )

    deadline: date

    skill_ids: list[str]


# ============================================================
# PROJECT RESPONSE

class ProjectResponse(BaseModel):
    """Schema response informasi proyek."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    umkm_id: str
    category_id: str
    title: str
    description: str
    budget: int
    deadline: date
    status: str

    published_at: UtcDateTime | None = None
    started_at: UtcDateTime | None = None
    completed_at: UtcDateTime | None = None

    created_at: UtcDateTime | None = None
    updated_at: UtcDateTime | None = None


class UpdateProjectRequest(CreateProjectRequest):
    """Request untuk memperbarui seluruh field proyek."""

    model_config = ConfigDict(extra="forbid")

class PublicProjectsPageResponse(BaseModel):
    items: list[ProjectResponse]
    limit: int
    offset: int
    has_more: bool
