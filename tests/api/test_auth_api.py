from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_email_sender,
    get_google_token_verifier,
    get_token_service,
    get_uow,
)
from app.core.google import GoogleIdentity, GoogleLoginUnavailableError
from app.core.security import ScryptPasswordHasher
from app.core.tokens import JwtTokenService
from app.main import app
from app.modules.auth.domain.entities import EMAIL_RESEND_COOLDOWN, PASSWORD_RESET_TTL
from app.modules.auth.presentation.dependencies import (
    get_action_token_repository,
    get_revoked_token_repository,
)
from app.modules.users.application.dto import CreateAdminInput
from app.modules.users.application.use_cases import CreateAdmin
from app.modules.users.presentation.dependencies import get_user_repository
from tests.fakes import (
    FakeAuthActionTokenRepository,
    FakeEmailSender,
    FakeGoogleTokenVerifier,
    FakeRevokedTokenRepository,
    FakeUnitOfWork,
    FakeUserRepository,
)

SECRET = "secret-key-untuk-test-minimal-32-karakter"
PASSWORD = "KaryaHebat2024"
ADMIN_EMAIL = "admin@temukarya.id"
EMAIL = "rina.pratiwi@kulinerbandung.id"
INVALID_EMAIL = "Format email tidak valid (harus mengandung domain lengkap)"


def register_body(**overrides) -> dict:
    body = {
        "name": "Rina Pratiwi",
        "email": "rina.pratiwi@kulinerbandung.id",
        "phone_number": "0812-3456-7890",
        "password": PASSWORD,
        "password_confirmation": PASSWORD,
        "role": "UMKM",
        "terms_accepted": True,
    }
    return body | overrides


@pytest.fixture
def users():
    return FakeUserRepository()


@pytest.fixture
def emails():
    return FakeEmailSender()


@pytest.fixture
def action_tokens():
    return FakeAuthActionTokenRepository()


@pytest.fixture
def google():
    return FakeGoogleTokenVerifier()


@pytest.fixture
def client(users, emails, action_tokens, google):
    revoked, uow = FakeRevokedTokenRepository(), FakeUnitOfWork()
    app.dependency_overrides = {
        get_user_repository: lambda: users,
        get_revoked_token_repository: lambda: revoked,
        get_action_token_repository: lambda: action_tokens,
        get_email_sender: lambda: emails,
        get_google_token_verifier: lambda: google,
        get_uow: lambda: uow,
        get_token_service: lambda: JwtTokenService(SECRET),
    }
    CreateAdmin(users, ScryptPasswordHasher(), uow).execute(
        CreateAdminInput(name="Admin", email=ADMIN_EMAIL, password=PASSWORD)
    )
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides = {}


def register(client, **overrides):
    return client.post("/api/v1/auth/register", json=register_body(**overrides))


def login(client, email="rina.pratiwi@kulinerbandung.id", password=PASSWORD, path="/api/v1/auth/login"):
    return client.post(path, json={"email": email, "password": password})


def register_verified(client, **overrides):
    response = register(client, **overrides)
    sender = app.dependency_overrides[get_email_sender]()
    verified = client.post("/api/v1/auth/email/verify", json={"token": sender.last_token})
    assert verified.status_code == 200, verified.text
    return response


def token_of(client, **register_overrides) -> str:
    register_verified(client, **register_overrides)
    email = register_overrides.get("email", "rina.pratiwi@kulinerbandung.id")
    return login(client, email=email).json()["data"]["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def assert_error(response, status_code: int, message: str | None = None) -> dict:
    assert response.status_code == status_code, response.text
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert isinstance(body["message"], str) and body["message"]
    if message is not None:
        assert body["message"] == message
    return body


def field_errors(response) -> dict[str, str]:
    body = assert_error(response, 422, "Data yang dikirim tidak valid")
    return {err["field"]: err["message"] for err in body["errors"]}


class TestRegister:
    def test_success_returns_envelope_and_normalized_user(self, client):
        response = register(client, email="  Rina.Pratiwi@KulinerBandung.ID ", name="  Rina  ")

        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["message"] == "Registrasi berhasil, silakan cek email untuk verifikasi"
        user = body["data"]
        assert user["name"] == "Rina"
        assert user["email"] == "rina.pratiwi@kulinerbandung.id"
        assert user["phone_number"] == "+6281234567890"
        assert user["role"] == "UMKM"
        assert user["profile_image_url"] is None
        assert user["email_verified_at"] is None
        assert user["created_at"].endswith("Z")
        assert "password" not in user and "password_hash" not in user

    def test_freelancer_can_register(self, client):
        assert register(client, role="FREELANCER").json()["data"]["role"] == "FREELANCER"

    @pytest.mark.parametrize(
        "phone",
        [
            "081234567890",
            "81234567890",
            "+6281234567890",
            "6281234567890",
            "0812 3456 7890",
            "0812-3456-7890",
            "+62 0812-3456-7890",
        ],
    )
    def test_phone_number_formats_are_normalized(self, client, phone):
        response = register(client, phone_number=phone)

        assert response.json()["data"]["phone_number"] == "+6281234567890"

    def test_duplicate_email_is_conflict(self, client):
        register(client)

        response = register(client, email="RINA.PRATIWI@kulinerbandung.id")

        assert_error(response, 409, "Email rina.pratiwi@kulinerbandung.id sudah terdaftar")

    def test_admin_role_is_forbidden(self, client):
        assert_error(
            register(client, role="ADMIN"), 403, "Akun admin tidak dapat dibuat melalui registrasi"
        )

    def test_empty_body_lists_every_required_field(self, client):
        errors = field_errors(client.post("/api/v1/auth/register", json={}))

        assert set(errors) == {
            "name",
            "email",
            "phone_number",
            "password",
            "password_confirmation",
            "role",
            "terms_accepted",
        }
        assert set(errors.values()) == {"Wajib diisi"}

    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [
            ("name", "   ", "Wajib diisi"),
            ("name", "a" * 101, "Maksimal 100 karakter"),
            ("email", "rina@", INVALID_EMAIL),
            ("email", "rina@kuliner", INVALID_EMAIL),
            ("email", "rina pratiwi@mail.com", INVALID_EMAIL),
            ("phone_number", "12345", "Nomor WhatsApp tidak valid, contoh: 081234567890"),
            ("phone_number", "0212345678", "Nomor WhatsApp tidak valid, contoh: 081234567890"),
            ("phone_number", "08abc", "Nomor WhatsApp tidak valid, contoh: 081234567890"),
            ("password", "pendek", "Minimal 8 karakter"),
            ("password", "a" * 129, "Maksimal 128 karakter"),
            ("name", 123, "Harus berupa teks"),
            ("terms_accepted", False, "Syarat & Ketentuan Layanan wajib disetujui"),
            ("terms_accepted", "bukan", "Harus berupa true atau false"),
        ],
    )
    def test_invalid_field(self, client, field, value, message):
        overrides = {field: value}
        if field == "password":
            overrides["password_confirmation"] = value

        assert field_errors(register(client, **overrides))[field] == message

    def test_password_confirmation_mismatch(self, client):
        errors = field_errors(register(client, password_confirmation="KaryaHebat2025"))

        assert errors == {"password_confirmation": "Konfirmasi kata sandi tidak sama dengan kata sandi"}

    def test_unknown_role(self, client):
        errors = field_errors(register(client, role="umkm"))

        assert errors["role"].startswith("Pilihan tidak valid")

    def test_invalid_json(self, client):
        response = client.post(
            "/api/v1/auth/register", content="{bukan json", headers={"Content-Type": "application/json"}
        )

        assert field_errors(response) == {"body": "Format JSON tidak valid"}

    def test_failed_registration_does_not_create_user(self, client, users):
        register(client, password_confirmation="beda12345")

        assert len(users.users) == 1


class TestLogin:
    def test_success_returns_token_and_user(self, client):
        register_verified(client)

        response = login(client, email=" RINA.Pratiwi@kulinerbandung.id ")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["message"] == "Login berhasil"
        assert body["data"]["token_type"] == "Bearer"
        assert body["data"]["access_token"]
        assert datetime.fromisoformat(body["data"]["expires_at"])
        assert body["data"]["user"]["role"] == "UMKM"
        assert body["data"]["user"]["email_verified_at"].endswith("Z")

    def test_unverified_email_is_forbidden_with_code(self, client):
        register(client)

        body = assert_error(
            login(client), 403, "Email belum diverifikasi, silakan cek email kamu"
        )

        assert body["code"] == "EMAIL_NOT_VERIFIED"

    def test_unverified_with_wrong_password_does_not_reveal_status(self, client):
        register(client)

        body = assert_error(login(client, password="SalahSandi1"), 401, "Email atau kata sandi salah")

        assert "code" not in body

    def test_wrong_password(self, client):
        register(client)

        assert_error(login(client, password="SalahSandi1"), 401, "Email atau kata sandi salah")

    def test_unknown_email_has_same_message_as_wrong_password(self, client):
        assert_error(login(client, email="tidakada@mail.com"), 401, "Email atau kata sandi salah")

    def test_admin_is_rejected_on_mobile_login(self, client):
        assert_error(
            login(client, email=ADMIN_EMAIL),
            403,
            "Akun admin hanya dapat login melalui dashboard admin",
        )

    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            ({}, {"email": "Wajib diisi", "password": "Wajib diisi"}),
            (
                {"email": "bukan-email", "password": "x"},
                {"email": INVALID_EMAIL},
            ),
            ({"email": "rina@mail.com", "password": ""}, {"password": "Wajib diisi"}),
        ],
    )
    def test_invalid_body(self, client, body, expected):
        assert field_errors(client.post("/api/v1/auth/login", json=body)) == expected


class TestAdminLogin:
    def test_admin_success(self, client):
        response = login(client, email=ADMIN_EMAIL, path="/api/v1/auth/admin/login")

        assert response.status_code == 200
        assert response.json()["message"] == "Login admin berhasil"
        assert response.json()["data"]["user"]["role"] == "ADMIN"

    @pytest.mark.parametrize("role", ["UMKM", "FREELANCER"])
    def test_non_admin_is_forbidden(self, client, role):
        register(client, role=role)

        assert_error(
            login(client, path="/api/v1/auth/admin/login"),
            403,
            "Akun ini tidak memiliki akses ke dashboard admin",
        )

    def test_wrong_password(self, client):
        assert_error(
            login(client, email=ADMIN_EMAIL, password="salah12345", path="/api/v1/auth/admin/login"),
            401,
            "Email atau kata sandi salah",
        )


class TestCurrentUser:
    def test_me_returns_current_user(self, client):
        token = token_of(client)

        response = client.get("/api/v1/auth/me", headers=auth(token))

        assert response.status_code == 200
        assert response.json()["message"] == "Data akun berhasil diambil"
        assert response.json()["data"]["email"] == "rina.pratiwi@kulinerbandung.id"

    @pytest.mark.parametrize(
        "headers",
        [{}, {"Authorization": ""}, {"Authorization": "Bearer"}, {"Authorization": "Basic abc"}],
    )
    def test_missing_token(self, client, headers):
        assert_error(client.get("/api/v1/auth/me", headers=headers), 401, "Silakan login terlebih dahulu")

    @pytest.mark.parametrize("token", ["abc", "a.b.c"])
    def test_invalid_token(self, client, token):
        assert_error(
            client.get("/api/v1/auth/me", headers=auth(token)),
            401,
            "Token tidak valid, silakan login kembali",
        )

    def test_token_signed_with_other_secret(self, client, users):
        user_id = next(iter(users.users))
        token = JwtTokenService("secret-lain-yang-juga-minimal-32-karakter").create_access_token(user_id)

        assert_error(client.get("/api/v1/auth/me", headers=auth(token.token)), 401)

    def test_expired_token(self, client, users):
        user_id = next(iter(users.users))
        token = JwtTokenService(SECRET, expire_minutes=-1).create_access_token(user_id).token

        assert_error(
            client.get("/api/v1/auth/me", headers=auth(token)),
            401,
            "Sesi sudah kedaluwarsa, silakan login kembali",
        )

    def test_token_of_deleted_account(self, client, users):
        token = token_of(client)
        users.users = {k: v for k, v in users.users.items() if v.email == ADMIN_EMAIL}

        assert_error(
            client.get("/api/v1/auth/me", headers=auth(token)),
            401,
            "Akun tidak ditemukan, silakan login kembali",
        )


class TestLogout:
    def test_logout_ends_session(self, client):
        token = token_of(client)

        response = client.post("/api/v1/auth/logout", headers=auth(token))

        assert response.status_code == 200
        assert response.json() == {"success": True, "message": "Logout berhasil", "data": None}
        assert_error(
            client.get("/api/v1/auth/me", headers=auth(token)),
            401,
            "Sesi sudah berakhir karena logout, silakan login kembali",
        )

    def test_logout_twice_is_unauthorized(self, client):
        token = token_of(client)
        client.post("/api/v1/auth/logout", headers=auth(token))

        assert_error(client.post("/api/v1/auth/logout", headers=auth(token)), 401)

    def test_logout_keeps_other_sessions(self, client):
        first = token_of(client)
        second = login(client).json()["data"]["access_token"]

        client.post("/api/v1/auth/logout", headers=auth(first))

        assert client.get("/api/v1/auth/me", headers=auth(second)).status_code == 200

    def test_logout_without_token(self, client):
        assert_error(client.post("/api/v1/auth/logout"), 401, "Silakan login terlebih dahulu")


class TestGetUser:
    def test_user_can_read_self(self, client):
        token = token_of(client)
        user_id = client.get("/api/v1/auth/me", headers=auth(token)).json()["data"]["id"]

        response = client.get(f"/api/v1/users/{user_id}", headers=auth(token))

        assert response.status_code == 200
        assert response.json()["data"]["id"] == user_id

    def test_user_cannot_read_other_user(self, client):
        other = token_of(client, email="andi@mail.com", role="FREELANCER")
        other_id = client.get("/api/v1/auth/me", headers=auth(other)).json()["data"]["id"]
        token = token_of(client)

        assert_error(
            client.get(f"/api/v1/users/{other_id}", headers=auth(token)),
            403,
            "Anda tidak memiliki akses ke data user ini",
        )

    def test_admin_can_read_any_user_and_gets_404_for_unknown(self, client):
        user_token = token_of(client)
        user_id = client.get("/api/v1/auth/me", headers=auth(user_token)).json()["data"]["id"]
        admin_token = login(client, email=ADMIN_EMAIL, path="/api/v1/auth/admin/login").json()["data"][
            "access_token"
        ]

        assert client.get(f"/api/v1/users/{user_id}", headers=auth(admin_token)).status_code == 200
        assert_error(client.get("/api/v1/users/tidak-ada", headers=auth(admin_token)), 404)

    def test_requires_login(self, client):
        assert_error(client.get("/api/v1/users/apa-saja"), 401)


class TestEnums:
    def test_list_all_enums(self, client):
        body = client.get("/api/v1/enums").json()

        assert body["success"] is True
        assert set(body["data"]) == {"user_roles", "registration_roles"}

    def test_registration_roles_exclude_admin(self, client):
        response = client.get("/api/v1/enums/registration_roles")

        assert response.status_code == 200
        assert response.json()["data"] == [
            {"value": "UMKM", "label": "Pemilik UMKM"},
            {"value": "FREELANCER", "label": "Freelancer Digital"},
        ]

    def test_unknown_enum(self, client):
        assert_error(client.get("/api/v1/enums/tidak_ada"), 404, "Enum tidak_ada tidak ditemukan")


class TestGenericErrors:
    def test_unknown_route(self, client):
        assert_error(client.get("/tidak-ada"), 404, "Endpoint tidak ditemukan")

    def test_wrong_method(self, client):
        assert_error(client.get("/api/v1/auth/login"), 405, "Metode HTTP tidak diizinkan untuk endpoint ini")

    def test_unexpected_error_is_wrapped(self, client):
        def broken_repository():
            raise RuntimeError("database mati")

        app.dependency_overrides[get_user_repository] = broken_repository

        assert_error(login(client), 500, "Terjadi kesalahan pada server, silakan coba lagi")


class TestEmailVerification:
    def test_register_sends_link_to_registered_address(self, client, emails):
        register(client)

        assert emails.sent[-1].to == EMAIL
        assert f"/api/v1/auth/email/verify?token={emails.last_token}" in emails.sent[-1].text

    def test_failed_register_sends_nothing(self, client, emails):
        register(client, password_confirmation="beda12345")

        assert emails.sent == []

    def test_verify_then_login(self, client, emails):
        register(client)

        response = client.post("/api/v1/auth/email/verify", json={"token": emails.last_token})

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "message": "Email berhasil diverifikasi, silakan login",
            "data": None,
        }
        assert login(client).status_code == 200

    def test_opening_link_twice_stays_successful(self, client, emails):
        register(client)
        client.post("/api/v1/auth/email/verify", json={"token": emails.last_token})

        assert client.post("/api/v1/auth/email/verify", json={"token": emails.last_token}).status_code == 200

    def test_unknown_token(self, client):
        assert_error(
            client.post("/api/v1/auth/email/verify", json={"token": "tidak-ada"}),
            400,
            "Tautan verifikasi tidak valid atau sudah digunakan",
        )

    def test_expired_token(self, client, emails, action_tokens):
        register(client)
        action_tokens.shift_all(-timedelta(hours=24))

        assert_error(
            client.post("/api/v1/auth/email/verify", json={"token": emails.last_token}),
            400,
            "Tautan verifikasi sudah kedaluwarsa, silakan minta tautan baru",
        )
        assert login(client).status_code == 403

    @pytest.mark.parametrize(
        ("body", "message"),
        [({}, "Wajib diisi"), ({"token": "  "}, "Wajib diisi"), ({"token": "a" * 513}, "Maksimal 512 karakter")],
    )
    def test_invalid_body(self, client, body, message):
        assert field_errors(client.post("/api/v1/auth/email/verify", json=body)) == {"token": message}

    def test_link_page_is_html_without_token_and_does_not_verify(self, client, emails, users):
        register(client)
        token = emails.last_token

        response = client.get(f"/api/v1/auth/email/verify?token={token}")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["cache-control"] == "no-store"
        assert token not in response.text
        assert users.get_by_email(EMAIL).email_verified_at is None


class TestResendVerification:
    MESSAGE = "Jika email perlu diverifikasi, tautan baru sudah dikirim"

    def resend(self, client, email=EMAIL):
        return client.post("/api/v1/auth/email/resend", json={"email": email})

    def test_after_cooldown_sends_new_link(self, client, emails, action_tokens):
        register(client)
        old_token = emails.last_token
        action_tokens.shift_all(-EMAIL_RESEND_COOLDOWN)

        response = self.resend(client)

        assert response.status_code == 200
        assert response.json()["message"] == self.MESSAGE
        assert len(emails.sent) == 2
        assert_error(client.post("/api/v1/auth/email/verify", json={"token": old_token}), 400)
        assert client.post("/api/v1/auth/email/verify", json={"token": emails.last_token}).status_code == 200

    def test_same_response_for_every_case_without_extra_email(self, client, emails):
        register(client)
        register_verified(client, email="andi@mail.com")
        before = len(emails.sent)

        responses = [
            self.resend(client),
            self.resend(client, "andi@mail.com"),
            self.resend(client, "tidakada@mail.com"),
        ]

        assert [r.status_code for r in responses] == [200, 200, 200]
        assert {r.json()["message"] for r in responses} == {self.MESSAGE}
        assert len(emails.sent) == before

    def test_invalid_email(self, client):
        assert field_errors(self.resend(client, "bukan-email")) == {"email": INVALID_EMAIL}


class TestForgotPassword:
    MESSAGE = "Jika email terdaftar, tautan reset sudah dikirim"

    def forgot(self, client, email=EMAIL):
        return client.post("/api/v1/auth/password/forgot", json={"email": email})

    def reset(self, client, token, password="SandiBaru2024", confirmation=None):
        return client.post(
            "/api/v1/auth/password/reset",
            json={
                "token": token,
                "password": password,
                "password_confirmation": confirmation or password,
            },
        )

    def test_same_response_for_registered_and_unknown_email(self, client, emails):
        register_verified(client)
        before = len(emails.sent)

        known = self.forgot(client)
        unknown = self.forgot(client, "tidakada@mail.com")

        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()
        assert known.json()["message"] == self.MESSAGE
        assert len(emails.sent) == before + 1
        assert f"/api/v1/auth/password/reset?token={emails.last_token}" in emails.sent[-1].text

    def test_within_cooldown_only_one_email(self, client, emails):
        register_verified(client)
        before = len(emails.sent)

        assert self.forgot(client).status_code == 200
        assert self.forgot(client).status_code == 200

        assert len(emails.sent) == before + 1

    def test_reset_full_flow_replaces_password_and_ends_old_session(self, client, emails, users):
        old_session = token_of(client)
        self.forgot(client)

        response = self.reset(client, emails.last_token)

        assert response.status_code == 200
        assert response.json()["message"] == "Kata sandi berhasil diubah, silakan login"
        assert_error(login(client), 401, "Email atau kata sandi salah")

        user = users.get_by_email(EMAIL)
        users.update_password(user.id, user.password_hash, datetime.now(UTC) + timedelta(seconds=2))
        assert_error(
            client.get("/api/v1/auth/me", headers=auth(old_session)),
            401,
            "Kata sandi telah diubah, silakan login kembali",
        )

    def test_login_with_new_password_right_after_reset(self, client, emails):
        register_verified(client)
        self.forgot(client)
        self.reset(client, emails.last_token)

        new_session = login(client, password="SandiBaru2024")

        assert new_session.status_code == 200
        token = new_session.json()["data"]["access_token"]
        assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 200

    def test_reset_verifies_unverified_account(self, client, emails):
        register(client)
        self.forgot(client)
        self.reset(client, emails.last_token)

        assert login(client, password="SandiBaru2024").status_code == 200

    def test_link_cannot_be_reused(self, client, emails):
        register_verified(client)
        self.forgot(client)
        token = emails.last_token
        self.reset(client, token)

        assert_error(
            self.reset(client, token, "SandiLain2024"),
            400,
            "Tautan reset tidak valid atau sudah digunakan",
        )

    def test_expired_link(self, client, emails, action_tokens):
        register_verified(client)
        self.forgot(client)
        action_tokens.shift_all(-PASSWORD_RESET_TTL)

        assert_error(
            self.reset(client, emails.last_token),
            400,
            "Tautan reset sudah kedaluwarsa, silakan minta tautan baru",
        )
        assert login(client).status_code == 200

    def test_unknown_link(self, client):
        assert_error(self.reset(client, "tidak-ada"), 400, "Tautan reset tidak valid atau sudah digunakan")

    @pytest.mark.parametrize(
        ("password", "confirmation", "expected"),
        [
            ("pendek", "pendek", {"password": "Minimal 8 karakter"}),
            (
                "SandiBaru2024",
                "SandiBeda2024",
                {"password_confirmation": "Konfirmasi kata sandi tidak sama dengan kata sandi"},
            ),
        ],
    )
    def test_invalid_new_password_does_not_use_up_link(
        self, client, emails, password, confirmation, expected
    ):
        register_verified(client)
        self.forgot(client)

        response = self.reset(client, emails.last_token, password, confirmation)

        assert field_errors(response) == expected
        assert self.reset(client, emails.last_token).status_code == 200

    def test_empty_body(self, client):
        assert set(field_errors(client.post("/api/v1/auth/password/reset", json={}))) == {
            "token",
            "password",
            "password_confirmation",
        }
        assert field_errors(client.post("/api/v1/auth/password/forgot", json={})) == {"email": "Wajib diisi"}

    def test_invalid_email(self, client):
        assert field_errors(self.forgot(client, "bukan-email")) == {"email": INVALID_EMAIL}

    def test_link_page_has_password_form_without_token(self, client, emails):
        register_verified(client)
        self.forgot(client)

        response = client.get(f"/api/v1/auth/password/reset?token={emails.last_token}")

        assert response.status_code == 200
        assert 'name="password_confirmation"' in response.text
        assert emails.last_token not in response.text


class TestGoogleLogin:
    TOKEN = "google-id-token"

    def google_login(self, client, token=TOKEN):
        return client.post("/api/v1/auth/google", json={"id_token": token})

    def test_registered_account_gets_session(self, client, google):
        register_verified(client)
        google.identities[self.TOKEN] = GoogleIdentity(EMAIL, True)

        response = self.google_login(client)

        assert response.status_code == 200
        assert response.json()["message"] == "Login berhasil"
        token = response.json()["data"]["access_token"]
        assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 200

    def test_unverified_account_is_claimed_and_old_password_stops_working(self, client, google):
        register(client)
        google.identities[self.TOKEN] = GoogleIdentity(EMAIL, True)

        response = self.google_login(client)

        assert response.json()["data"]["user"]["email_verified_at"].endswith("Z")
        assert_error(login(client), 401, "Email atau kata sandi salah")

    def test_unregistered_account(self, client, google):
        google.identities[self.TOKEN] = GoogleIdentity("baru@mail.com", True)

        assert_error(
            self.google_login(client),
            404,
            "Akun Google ini belum terdaftar, silakan daftar terlebih dahulu",
        )

    def test_google_email_not_verified(self, client, google):
        register_verified(client)
        google.identities[self.TOKEN] = GoogleIdentity(EMAIL, False)

        assert_error(self.google_login(client), 403, "Email akun Google ini belum terverifikasi")

    def test_invalid_token(self, client):
        assert_error(
            self.google_login(client, "palsu"),
            401,
            "Token Google tidak valid, silakan coba masuk kembali",
        )

    def test_admin_is_rejected(self, client, google):
        google.identities[self.TOKEN] = GoogleIdentity(ADMIN_EMAIL, True)

        assert_error(
            self.google_login(client), 403, "Akun admin hanya dapat login melalui dashboard admin"
        )

    def test_unavailable(self, client):
        class Offline(FakeGoogleTokenVerifier):
            def verify(self, id_token):
                raise GoogleLoginUnavailableError()

        app.dependency_overrides[get_google_token_verifier] = Offline

        assert_error(
            self.google_login(client),
            503,
            "Login Google sedang tidak tersedia, silakan masuk dengan email",
        )

    def test_empty_token(self, client):
        assert field_errors(client.post("/api/v1/auth/google", json={})) == {"id_token": "Wajib diisi"}
