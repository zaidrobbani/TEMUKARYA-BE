from app.core.exceptions import NotFoundError


class EnumNotFoundError(NotFoundError):
    def __init__(self, name: str):
        super().__init__(f"Enum {name} tidak ditemukan")
