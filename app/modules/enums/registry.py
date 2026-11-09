from dataclasses import dataclass

from app.modules.users.domain.entities import SELF_REGISTRABLE_ROLES, UserRole


@dataclass(frozen=True)
class EnumOption:
    value: str
    label: str


_USER_ROLE_LABELS: dict[UserRole, str] = {
    UserRole.UMKM: "Pemilik UMKM",
    UserRole.FREELANCER: "Freelancer Digital",
    UserRole.ADMIN: "Admin",
}

ENUMS: dict[str, list[EnumOption]] = {
    "user_roles": [EnumOption(role.value, label) for role, label in _USER_ROLE_LABELS.items()],
    "registration_roles": [
        EnumOption(role.value, label)
        for role, label in _USER_ROLE_LABELS.items()
        if role in SELF_REGISTRABLE_ROLES
    ],
}
