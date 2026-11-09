from pydantic import BaseModel

from app.core.responses import UtcDateTime
from app.modules.users.domain.entities import UserRole


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    phone_number: str | None
    role: UserRole
    profile_image_url: str | None
    email_verified_at: UtcDateTime | None
    created_at: UtcDateTime
