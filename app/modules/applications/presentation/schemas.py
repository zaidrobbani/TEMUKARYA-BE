from pydantic import BaseModel, ConfigDict, Field

from app.core.responses import UtcDateTime


class SubmitApplicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposed_price: int = Field(
        strict=True,
        ge=1,
        le=(2**64) - 1,
    )

    estimated_duration_days: int = Field(
        strict=True,
        ge=1,
        le=(2**32) - 1,
    )

    proposal_message: str = Field(
        min_length=1,
        max_length=5000,
    )


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    freelancer_id: str

    proposed_price: int
    estimated_duration_days: int
    proposal_message: str
    status: str

    submitted_at: UtcDateTime | None = None
    created_at: UtcDateTime | None = None
    updated_at: UtcDateTime | None = None


class ApplicationsPageResponse(BaseModel):
    items: list[ApplicationResponse]
    limit: int
    offset: int
    has_more: bool
