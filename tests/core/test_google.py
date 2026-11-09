from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.google import (
    GoogleLoginUnavailableError,
    InvalidGoogleTokenError,
    JwtGoogleTokenVerifier,
)

CLIENT_ID = "temukarya-web.apps.googleusercontent.com"
GOOGLE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class StubJwksClient:
    def get_signing_key_from_jwt(self, token: str):
        jwt.get_unverified_header(token)
        return SimpleNamespace(key=GOOGLE_KEY.public_key())


class OfflineJwksClient:
    def get_signing_key_from_jwt(self, token: str):
        raise jwt.PyJWKClientConnectionError("tidak terhubung")


def id_token(key=GOOGLE_KEY, **overrides) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1234567890",
        "email": "rina@mail.com",
        "email_verified": True,
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    claims.update(overrides)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, key, algorithm="RS256")


@pytest.fixture
def verifier():
    return JwtGoogleTokenVerifier(CLIENT_ID, StubJwksClient())


@pytest.mark.parametrize("issuer", ["https://accounts.google.com", "accounts.google.com"])
def test_valid_token_returns_identity(verifier, issuer):
    identity = verifier.verify(id_token(iss=issuer))

    assert identity.email == "rina@mail.com"
    assert identity.email_verified is True


@pytest.mark.parametrize(("claim", "expected"), [(False, False), ("true", True), (None, False)])
def test_email_verified_claim_variants(verifier, claim, expected):
    assert verifier.verify(id_token(email_verified=claim)).email_verified is expected


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(id_token(aud="aplikasi-lain"), id="audience lain"),
        pytest.param(id_token(iss="https://bukan-google.com"), id="issuer lain"),
        pytest.param(
            id_token(exp=datetime.now(UTC) - timedelta(minutes=5)),
            id="kedaluwarsa",
        ),
        pytest.param(id_token(key=OTHER_KEY), id="tanda tangan kunci lain"),
        pytest.param(id_token(email=None), id="tanpa email"),
        pytest.param(jwt.encode({"email": "a@b.co"}, "", algorithm="none"), id="alg none"),
        pytest.param("bukan-jwt", id="bukan jwt"),
    ],
)
def test_rejected_tokens(verifier, token):
    with pytest.raises(InvalidGoogleTokenError):
        verifier.verify(token)


def test_unconfigured_client_id_is_unavailable():
    with pytest.raises(GoogleLoginUnavailableError):
        JwtGoogleTokenVerifier("", StubJwksClient()).verify(id_token())


def test_google_keys_unreachable_is_unavailable():
    with pytest.raises(GoogleLoginUnavailableError):
        JwtGoogleTokenVerifier(CLIENT_ID, OfflineJwksClient()).verify(id_token())
