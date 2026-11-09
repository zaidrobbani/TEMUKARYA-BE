from abc import ABC, abstractmethod
from dataclasses import dataclass

import jwt

from app.core.exceptions import ServiceUnavailableError, UnauthorizedError

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")


class InvalidGoogleTokenError(UnauthorizedError):
    def __init__(self):
        super().__init__("Token Google tidak valid, silakan coba masuk kembali")


class GoogleLoginUnavailableError(ServiceUnavailableError):
    def __init__(self):
        super().__init__("Login Google sedang tidak tersedia, silakan masuk dengan email")


@dataclass(frozen=True)
class GoogleIdentity:
    email: str
    email_verified: bool


class GoogleTokenVerifier(ABC):
    @abstractmethod
    def verify(self, id_token: str) -> GoogleIdentity: ...


class JwtGoogleTokenVerifier(GoogleTokenVerifier):
    def __init__(self, client_id: str, jwks_client: jwt.PyJWKClient):
        self._client_id = client_id
        self._jwks_client = jwks_client

    def verify(self, id_token: str) -> GoogleIdentity:
        if not self._client_id:
            raise GoogleLoginUnavailableError()

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(id_token)
            payload = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._client_id,
                issuer=GOOGLE_ISSUERS,
                options={"require": ["exp", "iat", "aud", "iss", "email"]},
            )
        except jwt.PyJWKClientConnectionError as exc:
            raise GoogleLoginUnavailableError() from exc
        except jwt.PyJWTError as exc:
            raise InvalidGoogleTokenError() from exc

        return GoogleIdentity(
            email=payload["email"],
            email_verified=str(payload.get("email_verified")).lower() == "true",
        )
