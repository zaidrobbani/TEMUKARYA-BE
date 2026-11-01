from dataclasses import dataclass

from app.core.exceptions import UnauthorizedError
from app.modules.users.domain.entities import UserRole


@dataclass(frozen=True)
class AuthenticatedProfileUser:
    user_id: str
    role: UserRole


def get_authenticated_profile_user() -> AuthenticatedProfileUser:
    # Sementara ditutup sampai integrasi JWT Zaid tersedia.
    raise UnauthorizedError(
        "Authentication belum terintegrasi"
    )