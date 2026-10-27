from app.core.exceptions import ConflictError, NotFoundError


class UserNotFoundError(NotFoundError):
    def __init__(self, user_id: int):
        super().__init__(f"User {user_id} tidak ditemukan")


class EmailAlreadyRegisteredError(ConflictError):
    def __init__(self, email: str):
        super().__init__(f"Email {email} sudah terdaftar")
