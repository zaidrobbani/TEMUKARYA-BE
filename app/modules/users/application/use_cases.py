from app.core.security import PasswordHasher
from app.core.unit_of_work import UnitOfWork
from app.modules.users.application.dto import RegisterUserInput
from app.modules.users.domain.entities import User
from app.modules.users.domain.exceptions import EmailAlreadyRegisteredError, UserNotFoundError
from app.modules.users.domain.repositories import UserRepository



class RegisterUser:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, uow: UnitOfWork):
        self._users = users
        self._hasher = hasher
        self._uow = uow

    def execute(self, data: RegisterUserInput) -> User:
        email = data.email.strip().lower()
        if self._users.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError(email)

        user = self._users.add(
            User(
                name=data.name.strip(),
                email=email,
                password_hash=self._hasher.hash(data.password),
                role=data.role,
            )
        )
        self._uow.commit()
        return user


class GetUser:
    def __init__(self, users: UserRepository):
        self._users = users

    def execute(self, user_id: str) -> User:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user
