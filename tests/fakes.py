import re
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from app.core.email import EmailMessage, EmailSender
from app.core.google import GoogleIdentity, GoogleTokenVerifier, InvalidGoogleTokenError
from app.core.unit_of_work import UnitOfWork
from app.modules.auth.domain.entities import AuthActionPurpose, AuthActionToken
from app.modules.auth.domain.repositories import AuthActionTokenRepository, RevokedTokenRepository
from app.modules.users.domain.entities import User
from app.modules.users.domain.repositories import UserRepository


class FakeUserRepository(UserRepository):
    def __init__(self):
        self.users: dict[str, User] = {}

    def get_by_id(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    def add(self, user: User) -> User:
        now = datetime.now(UTC)
        saved = replace(user, id=str(uuid4()), created_at=now, updated_at=now)
        self.users[saved.id] = saved
        return saved

    def mark_email_verified(self, user_id: str, verified_at: datetime) -> None:
        self.users[user_id] = replace(self.users[user_id], email_verified_at=verified_at)

    def update_password(self, user_id: str, password_hash: str, changed_at: datetime) -> None:
        self.users[user_id] = replace(
            self.users[user_id], password_hash=password_hash, password_changed_at=changed_at
        )


class FakeRevokedTokenRepository(RevokedTokenRepository):
    def __init__(self):
        self.tokens: dict[str, tuple[str, datetime]] = {}

    def add(self, jti: str, user_id: str, expires_at: datetime) -> None:
        self.tokens.setdefault(jti, (user_id, expires_at))

    def exists(self, jti: str) -> bool:
        return jti in self.tokens


class FakeAuthActionTokenRepository(AuthActionTokenRepository):
    def __init__(self):
        self.tokens: dict[str, AuthActionToken] = {}

    def add(self, token: AuthActionToken) -> None:
        saved = replace(token, id=str(uuid4()))
        self.tokens[saved.id] = saved

    def get_by_hash(self, token_hash: str, purpose: AuthActionPurpose) -> AuthActionToken | None:
        return next(
            (
                t
                for t in self.tokens.values()
                if t.token_hash == token_hash and t.purpose == purpose
            ),
            None,
        )

    def latest_created_at(self, user_id: str, purpose: AuthActionPurpose) -> datetime | None:
        return max(
            (
                t.created_at
                for t in self.tokens.values()
                if t.user_id == user_id and t.purpose == purpose
            ),
            default=None,
        )

    def invalidate_active(self, user_id: str, purpose: AuthActionPurpose, at: datetime) -> None:
        for token in list(self.tokens.values()):
            if token.user_id == user_id and token.purpose == purpose and token.used_at is None:
                self.tokens[token.id] = replace(token, used_at=at)

    def consume(self, token_id: str, at: datetime) -> bool:
        token = self.tokens[token_id]
        if token.used_at is not None:
            return False
        self.tokens[token_id] = replace(token, used_at=at)
        return True

    def shift_all(self, delta) -> None:
        """Mundurkan waktu semua token untuk mensimulasikan kedaluwarsa dan jeda kirim ulang."""
        for token in list(self.tokens.values()):
            self.tokens[token.id] = replace(
                token,
                created_at=token.created_at + delta,
                expires_at=token.expires_at + delta,
            )


class FakeEmailSender(EmailSender):
    def __init__(self):
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.sent.append(message)

    @property
    def last_token(self) -> str:
        return re.search(r"token=([\w-]+)", self.sent[-1].text).group(1)


class FakeGoogleTokenVerifier(GoogleTokenVerifier):
    def __init__(self):
        self.identities: dict[str, GoogleIdentity] = {}

    def verify(self, id_token: str) -> GoogleIdentity:
        if id_token not in self.identities:
            raise InvalidGoogleTokenError()
        return self.identities[id_token]


class FakeUnitOfWork(UnitOfWork):
    def __init__(self):
        self.commits = 0

    @property
    def committed(self) -> bool:
        return self.commits > 0

    def commit(self) -> None:
        self.commits += 1
