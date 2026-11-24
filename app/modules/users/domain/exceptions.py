from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError


class UserNotFoundError(NotFoundError):
    def __init__(self, user_id: str):
        super().__init__(f"User {user_id} tidak ditemukan")


class EmailAlreadyRegisteredError(ConflictError):
    def __init__(self, email: str):
        super().__init__(f"Email {email} sudah terdaftar")


class RoleNotRegistrableError(ForbiddenError):
    def __init__(self):
        super().__init__("Akun admin tidak dapat dibuat melalui registrasi")


class UserAccessDeniedError(ForbiddenError):
    def __init__(self):
        super().__init__("Anda tidak memiliki akses ke data user ini")
