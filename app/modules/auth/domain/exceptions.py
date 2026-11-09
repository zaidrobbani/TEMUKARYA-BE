from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError, UnauthorizedError
from app.modules.auth.domain.entities import LoginPortal

_PORTAL_DENIED_MESSAGES: dict[LoginPortal, str] = {
    LoginPortal.MOBILE_APP: "Akun admin hanya dapat login melalui dashboard admin",
    LoginPortal.ADMIN_DASHBOARD: "Akun ini tidak memiliki akses ke dashboard admin",
}


class InvalidCredentialsError(UnauthorizedError):
    def __init__(self):
        super().__init__("Email atau kata sandi salah")


class NotAuthenticatedError(UnauthorizedError):
    def __init__(self):
        super().__init__("Silakan login terlebih dahulu")


class SessionRevokedError(UnauthorizedError):
    def __init__(self):
        super().__init__("Sesi sudah berakhir karena logout, silakan login kembali")


class AccountNotFoundError(UnauthorizedError):
    def __init__(self):
        super().__init__("Akun tidak ditemukan, silakan login kembali")


class PortalAccessDeniedError(ForbiddenError):
    def __init__(self, portal: LoginPortal):
        super().__init__(_PORTAL_DENIED_MESSAGES[portal])


class InsufficientRoleError(ForbiddenError):
    def __init__(self):
        super().__init__("Anda tidak memiliki akses ke fitur ini")


class EmailNotVerifiedError(ForbiddenError):
    code = "EMAIL_NOT_VERIFIED"

    def __init__(self):
        super().__init__("Email belum diverifikasi, silakan cek email kamu")


class PasswordChangedError(UnauthorizedError):
    def __init__(self):
        super().__init__("Kata sandi telah diubah, silakan login kembali")


class InvalidVerificationLinkError(BadRequestError):
    def __init__(self):
        super().__init__("Tautan verifikasi tidak valid atau sudah digunakan")


class ExpiredVerificationLinkError(BadRequestError):
    def __init__(self):
        super().__init__("Tautan verifikasi sudah kedaluwarsa, silakan minta tautan baru")


class InvalidResetLinkError(BadRequestError):
    def __init__(self):
        super().__init__("Tautan reset tidak valid atau sudah digunakan")


class ExpiredResetLinkError(BadRequestError):
    def __init__(self):
        super().__init__("Tautan reset sudah kedaluwarsa, silakan minta tautan baru")


class GoogleEmailNotVerifiedError(ForbiddenError):
    def __init__(self):
        super().__init__("Email akun Google ini belum terverifikasi")


class GoogleAccountNotRegisteredError(NotFoundError):
    def __init__(self):
        super().__init__("Akun Google ini belum terdaftar, silakan daftar terlebih dahulu")
