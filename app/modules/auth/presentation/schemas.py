import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, StringConstraints, ValidationInfo, field_validator

from app.core.responses import UtcDateTime
from app.modules.users.domain.entities import UserRole
from app.modules.users.presentation.schemas import UserResponse

_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}")
_PHONE_SEPARATORS = re.compile(r"[\s\-.()]")
_PHONE_PATTERN = re.compile(r"(?:\+?62)?0?(8\d{8,11})")


def _validate_email(value: str) -> str:
    if not _EMAIL_PATTERN.fullmatch(value):
        raise ValueError("Format email tidak valid (harus mengandung domain lengkap)")
    return value


def _normalize_phone_number(value: str) -> str:
    match = _PHONE_PATTERN.fullmatch(_PHONE_SEPARATORS.sub("", value))
    if match is None:
        raise ValueError("Nomor WhatsApp tidak valid, contoh: 081234567890")
    return f"+62{match.group(1)}"


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, min_length=1, max_length=255),
    AfterValidator(_validate_email),
]
PhoneNumber = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20),
    AfterValidator(_normalize_phone_number),
]
NewPassword = Annotated[str, StringConstraints(min_length=8, max_length=128)]
Password = Annotated[str, StringConstraints(min_length=1, max_length=128)]
ActionToken = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]
GoogleIdToken = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)]


class _NewPasswordFields(BaseModel):
    password: NewPassword
    password_confirmation: Password

    @field_validator("password_confirmation")
    @classmethod
    def _passwords_match(cls, value: str, info: ValidationInfo) -> str:
        if "password" in info.data and value != info.data["password"]:
            raise ValueError("Konfirmasi kata sandi tidak sama dengan kata sandi")
        return value


class RegisterRequest(_NewPasswordFields):
    name: Name
    email: Email
    phone_number: PhoneNumber
    role: UserRole
    terms_accepted: bool

    @field_validator("terms_accepted")
    @classmethod
    def _terms_must_be_accepted(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Syarat & Ketentuan Layanan wajib disetujui")
        return value


class LoginRequest(BaseModel):
    email: Email
    password: Password


class GoogleLoginRequest(BaseModel):
    id_token: GoogleIdToken


class EmailRequest(BaseModel):
    email: Email


class VerifyEmailRequest(BaseModel):
    token: ActionToken


class ResetPasswordRequest(_NewPasswordFields):
    token: ActionToken


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_at: UtcDateTime
    user: UserResponse
