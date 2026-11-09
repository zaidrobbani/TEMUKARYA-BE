from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.tokens import ExpiredTokenError, InvalidTokenError, JwtTokenService

SECRET = "secret-key-untuk-test-minimal-32-karakter"


def test_access_token_round_trip():
    service = JwtTokenService(SECRET, expire_minutes=30)

    access = service.create_access_token("user-1")
    claims = service.decode_access_token(access.token)

    assert claims.user_id == "user-1"
    assert claims.jti == access.jti
    assert claims.expires_at == access.expires_at
    assert timedelta(minutes=29) < claims.expires_at - datetime.now(UTC) <= timedelta(minutes=30)


def test_each_token_has_unique_jti():
    service = JwtTokenService(SECRET)

    assert service.create_access_token("u").jti != service.create_access_token("u").jti


def test_expired_token_raises_expired_error():
    token = JwtTokenService(SECRET, expire_minutes=-1).create_access_token("user-1").token

    with pytest.raises(ExpiredTokenError):
        JwtTokenService(SECRET).decode_access_token(token)


def test_token_signed_with_other_secret_is_invalid():
    token = JwtTokenService("secret-lain-yang-juga-minimal-32-karakter").create_access_token("u").token

    with pytest.raises(InvalidTokenError):
        JwtTokenService(SECRET).decode_access_token(token)


def test_tampered_token_is_invalid():
    token = JwtTokenService(SECRET).create_access_token("u").token
    header, payload, signature = token.split(".")

    with pytest.raises(InvalidTokenError):
        JwtTokenService(SECRET).decode_access_token(f"{header}.{payload}x.{signature}")


@pytest.mark.parametrize("token", ["", "abc", "a.b.c"])
def test_malformed_token_is_invalid(token):
    with pytest.raises(InvalidTokenError):
        JwtTokenService(SECRET).decode_access_token(token)


@pytest.mark.parametrize("missing", ["sub", "jti", "iat", "exp"])
def test_token_without_required_claim_is_invalid(missing):
    now = datetime.now(UTC)
    payload = {"sub": "u", "jti": "j", "iat": now, "exp": now + timedelta(minutes=5)}
    payload.pop(missing)

    with pytest.raises(InvalidTokenError):
        JwtTokenService(SECRET).decode_access_token(jwt.encode(payload, SECRET, algorithm="HS256"))


def test_unsigned_token_is_rejected():
    now = datetime.now(UTC)
    payload = {"sub": "u", "jti": "j", "iat": now, "exp": now + timedelta(minutes=5)}

    with pytest.raises(InvalidTokenError):
        JwtTokenService(SECRET).decode_access_token(jwt.encode(payload, None, algorithm="none"))
