from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from app.core.exceptions import UnauthorizedError


class InvalidTokenError(UnauthorizedError):
    def __init__(self):
        super().__init__("Token tidak valid, silakan login kembali")


class ExpiredTokenError(UnauthorizedError):
    def __init__(self):
        super().__init__("Sesi sudah kedaluwarsa, silakan login kembali")


@dataclass(frozen=True)
class AccessToken:
    token: str
    jti: str
    expires_at: datetime


@dataclass(frozen=True)
class TokenClaims:
    user_id: str
    jti: str
    issued_at: datetime
    expires_at: datetime


class TokenService(ABC):
    @abstractmethod
    def create_access_token(self, user_id: str) -> AccessToken: ...

    @abstractmethod
    def decode_access_token(self, token: str) -> TokenClaims: ...


class JwtTokenService(TokenService):
    def __init__(self, secret_key: str, algorithm: str = "HS256", expire_minutes: int = 60 * 24):
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._expire_minutes = expire_minutes

    def create_access_token(self, user_id: str) -> AccessToken:
        issued_at = datetime.now(UTC)
        expires_at = issued_at + timedelta(minutes=self._expire_minutes)
        jti = str(uuid4())
        payload = {"sub": user_id, "jti": jti, "iat": issued_at, "exp": expires_at}
        token = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return AccessToken(token=token, jti=jti, expires_at=expires_at.replace(microsecond=0))

    def decode_access_token(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options={"require": ["sub", "jti", "iat", "exp"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise ExpiredTokenError() from exc
        except jwt.PyJWTError as exc:
            raise InvalidTokenError() from exc

        return TokenClaims(
            user_id=payload["sub"],
            jti=payload["jti"],
            issued_at=datetime.fromtimestamp(payload["iat"], UTC),
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
