from datetime import UTC, datetime, timedelta

import pytest

from app.core.google import GoogleIdentity, InvalidGoogleTokenError
from app.core.security import ScryptPasswordHasher
from app.core.tokens import ExpiredTokenError, InvalidTokenError, JwtTokenService
from app.modules.auth.application.dto import LoginInput
from app.modules.auth.application.use_cases import (
    AuthenticateToken,
    LoginUser,
    LoginWithGoogle,
    LogoutUser,
    RegisterAccount,
    RequestPasswordReset,
    ResendEmailVerification,
    ResetPassword,
    SendEmailVerification,
    VerifyEmail,
)
from app.modules.auth.domain.entities import (
    EMAIL_RESEND_COOLDOWN,
    EMAIL_VERIFICATION_TTL,
    PASSWORD_RESET_TTL,
    AuthActionPurpose,
    LoginPortal,
    hash_action_token,
)
from app.modules.auth.domain.exceptions import (
    AccountNotFoundError,
    EmailNotVerifiedError,
    ExpiredResetLinkError,
    ExpiredVerificationLinkError,
    GoogleAccountNotRegisteredError,
    GoogleEmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidResetLinkError,
    InvalidVerificationLinkError,
    PasswordChangedError,
    PortalAccessDeniedError,
    SessionRevokedError,
)
from app.modules.users.application.dto import RegisterUserInput
from app.modules.users.application.use_cases import RegisterUser
from app.modules.users.domain.entities import User, UserRole
from tests.fakes import (
    FakeAuthActionTokenRepository,
    FakeEmailSender,
    FakeGoogleTokenVerifier,
    FakeRevokedTokenRepository,
    FakeUnitOfWork,
    FakeUserRepository,
)

SECRET = "secret-key-untuk-test-minimal-32-karakter"
PASSWORD = "rahasia123"
BASE_URL = "https://api.temukarya.id"


@pytest.fixture
def hasher():
    return ScryptPasswordHasher()


@pytest.fixture
def tokens():
    return JwtTokenService(SECRET)


@pytest.fixture
def users():
    return FakeUserRepository()


@pytest.fixture
def revoked():
    return FakeRevokedTokenRepository()


@pytest.fixture
def action_tokens():
    return FakeAuthActionTokenRepository()


@pytest.fixture
def emails():
    return FakeEmailSender()


def add_user(users, hasher, role=UserRole.UMKM, email="budi@mail.com", verified=True) -> User:
    return users.add(
        User(
            name="Budi",
            email=email,
            password_hash=hasher.hash(PASSWORD),
            role=role,
            email_verified_at=datetime.now(UTC) if verified else None,
        )
    )


def send_verification(users, action_tokens, emails) -> SendEmailVerification:
    return SendEmailVerification(users, action_tokens, emails, FakeUnitOfWork(), BASE_URL)


def request_reset(users, action_tokens, emails) -> RequestPasswordReset:
    return RequestPasswordReset(users, action_tokens, emails, FakeUnitOfWork(), BASE_URL)


@pytest.mark.parametrize("role", [UserRole.UMKM, UserRole.FREELANCER])
def test_login_returns_token_for_user(users, hasher, tokens, role):
    user = add_user(users, hasher, role)

    result = LoginUser(users, hasher, tokens).execute(LoginInput("budi@mail.com", PASSWORD))

    assert result.user == user
    assert tokens.decode_access_token(result.access_token.token).user_id == user.id


def test_login_normalizes_email(users, hasher, tokens):
    user = add_user(users, hasher)

    result = LoginUser(users, hasher, tokens).execute(LoginInput("  BUDI@Mail.com ", PASSWORD))

    assert result.user == user


def test_login_rejects_wrong_password(users, hasher, tokens):
    add_user(users, hasher)

    with pytest.raises(InvalidCredentialsError):
        LoginUser(users, hasher, tokens).execute(LoginInput("budi@mail.com", "salah12345"))


def test_login_rejects_unknown_email_with_same_error(users, hasher, tokens):
    with pytest.raises(InvalidCredentialsError):
        LoginUser(users, hasher, tokens).execute(LoginInput("tidakada@mail.com", PASSWORD))


def test_login_rejects_password_with_different_case(users, hasher, tokens):
    add_user(users, hasher)

    with pytest.raises(InvalidCredentialsError):
        LoginUser(users, hasher, tokens).execute(LoginInput("budi@mail.com", PASSWORD.upper()))


def test_admin_cannot_login_through_mobile_app(users, hasher, tokens):
    add_user(users, hasher, UserRole.ADMIN)

    with pytest.raises(PortalAccessDeniedError):
        LoginUser(users, hasher, tokens).execute(LoginInput("budi@mail.com", PASSWORD))


def test_admin_can_login_through_admin_dashboard(users, hasher, tokens):
    admin = add_user(users, hasher, UserRole.ADMIN)

    result = LoginUser(users, hasher, tokens).execute(
        LoginInput("budi@mail.com", PASSWORD, LoginPortal.ADMIN_DASHBOARD)
    )

    assert result.user == admin


@pytest.mark.parametrize("role", [UserRole.UMKM, UserRole.FREELANCER])
def test_non_admin_cannot_login_through_admin_dashboard(users, hasher, tokens, role):
    add_user(users, hasher, role)

    with pytest.raises(PortalAccessDeniedError):
        LoginUser(users, hasher, tokens).execute(
            LoginInput("budi@mail.com", PASSWORD, LoginPortal.ADMIN_DASHBOARD)
        )


def test_admin_dashboard_wrong_password_does_not_reveal_role(users, hasher, tokens):
    add_user(users, hasher, UserRole.UMKM)

    with pytest.raises(InvalidCredentialsError):
        LoginUser(users, hasher, tokens).execute(
            LoginInput("budi@mail.com", "salah12345", LoginPortal.ADMIN_DASHBOARD)
        )


def test_authenticate_returns_session(users, hasher, tokens, revoked):
    user = add_user(users, hasher)
    access = tokens.create_access_token(user.id)

    session = AuthenticateToken(users, revoked, tokens).execute(access.token)

    assert session.user == user
    assert session.claims.jti == access.jti


def test_authenticate_rejects_invalid_token(users, revoked, tokens):
    with pytest.raises(InvalidTokenError):
        AuthenticateToken(users, revoked, tokens).execute("bukan-token")


def test_authenticate_rejects_expired_token(users, hasher, revoked, tokens):
    user = add_user(users, hasher)
    token = JwtTokenService(SECRET, expire_minutes=-1).create_access_token(user.id).token

    with pytest.raises(ExpiredTokenError):
        AuthenticateToken(users, revoked, tokens).execute(token)


def test_authenticate_rejects_token_of_deleted_user(users, hasher, revoked, tokens):
    user = add_user(users, hasher)
    token = tokens.create_access_token(user.id).token
    del users.users[user.id]

    with pytest.raises(AccountNotFoundError):
        AuthenticateToken(users, revoked, tokens).execute(token)


def test_logout_revokes_only_current_token(users, hasher, revoked, tokens):
    user = add_user(users, hasher)
    first = tokens.create_access_token(user.id).token
    second = tokens.create_access_token(user.id).token
    authenticate = AuthenticateToken(users, revoked, tokens)
    uow = FakeUnitOfWork()

    LogoutUser(revoked, uow).execute(authenticate.execute(first))

    assert uow.committed
    with pytest.raises(SessionRevokedError):
        authenticate.execute(first)
    assert authenticate.execute(second).user == user


def test_logout_twice_with_same_session_is_idempotent(users, hasher, revoked, tokens):
    user = add_user(users, hasher)
    session = AuthenticateToken(users, revoked, tokens).execute(
        tokens.create_access_token(user.id).token
    )
    use_case = LogoutUser(revoked, FakeUnitOfWork())

    use_case.execute(session)
    use_case.execute(session)

    assert len(revoked.tokens) == 1


class TestEmailVerificationRequired:
    def test_login_rejects_unverified_email_after_correct_password(self, users, hasher, tokens):
        add_user(users, hasher, verified=False)

        with pytest.raises(EmailNotVerifiedError) as exc_info:
            LoginUser(users, hasher, tokens).execute(LoginInput("budi@mail.com", PASSWORD))

        assert exc_info.value.code == "EMAIL_NOT_VERIFIED"

    def test_wrong_password_on_unverified_does_not_reveal_status(self, users, hasher, tokens):
        add_user(users, hasher, verified=False)

        with pytest.raises(InvalidCredentialsError):
            LoginUser(users, hasher, tokens).execute(LoginInput("budi@mail.com", "salah12345"))


class TestRegisterAccount:
    def test_new_account_is_unverified_and_gets_verification_email(
        self, users, hasher, action_tokens, emails
    ):
        uow = FakeUnitOfWork()
        use_case = RegisterAccount(
            RegisterUser(users, hasher, uow),
            SendEmailVerification(users, action_tokens, emails, uow, BASE_URL),
        )

        user = use_case.execute(
            RegisterUserInput(
                name="Budi", email="budi@mail.com", password=PASSWORD, role=UserRole.UMKM
            )
        )

        assert user.email_verified_at is None
        assert user.terms_accepted_at is not None
        assert emails.sent[-1].to == "budi@mail.com"
        assert f"{BASE_URL}/auth/email/verify?token={emails.last_token}" in emails.sent[-1].text
        stored = next(iter(action_tokens.tokens.values()))
        assert stored.purpose == AuthActionPurpose.EMAIL_VERIFICATION
        assert stored.expires_at - stored.created_at == EMAIL_VERIFICATION_TTL

    def test_raw_token_is_never_stored(self, users, hasher, action_tokens, emails):
        user = add_user(users, hasher, verified=False)

        send_verification(users, action_tokens, emails).execute(user)

        stored = next(iter(action_tokens.tokens.values()))
        assert stored.token_hash != emails.last_token
        assert stored.token_hash == hash_action_token(emails.last_token)


class TestVerifyEmail:
    def test_success_marks_verified_and_commits(self, users, hasher, action_tokens, emails):
        user = add_user(users, hasher, verified=False)
        send_verification(users, action_tokens, emails).execute(user)
        uow = FakeUnitOfWork()

        VerifyEmail(users, action_tokens, uow).execute(emails.last_token)

        assert users.get_by_id(user.id).email_verified_at is not None
        assert uow.committed

    def test_second_use_is_idempotent(self, users, hasher, action_tokens, emails):
        user = add_user(users, hasher, verified=False)
        send_verification(users, action_tokens, emails).execute(user)
        use_case = VerifyEmail(users, action_tokens, FakeUnitOfWork())

        use_case.execute(emails.last_token)
        use_case.execute(emails.last_token)

        assert users.get_by_id(user.id).email_verified_at is not None

    def test_unknown_token(self, users, action_tokens):
        with pytest.raises(InvalidVerificationLinkError):
            VerifyEmail(users, action_tokens, FakeUnitOfWork()).execute("tidak-ada")

    def test_expired_token(self, users, hasher, action_tokens, emails):
        user = add_user(users, hasher, verified=False)
        send_verification(users, action_tokens, emails).execute(user)
        action_tokens.shift_all(-EMAIL_VERIFICATION_TTL)

        with pytest.raises(ExpiredVerificationLinkError):
            VerifyEmail(users, action_tokens, FakeUnitOfWork()).execute(emails.last_token)

        assert users.get_by_id(user.id).email_verified_at is None

    def test_old_link_is_invalid_after_resend(self, users, hasher, action_tokens, emails):
        user = add_user(users, hasher, verified=False)
        sender = send_verification(users, action_tokens, emails)
        sender.execute(user)
        old_token = emails.last_token
        sender.execute(user)

        with pytest.raises(InvalidVerificationLinkError):
            VerifyEmail(users, action_tokens, FakeUnitOfWork()).execute(old_token)

    def test_reset_token_cannot_verify_email(self, users, hasher, action_tokens, emails):
        add_user(users, hasher, verified=False)
        request_reset(users, action_tokens, emails).execute("budi@mail.com")

        with pytest.raises(InvalidVerificationLinkError):
            VerifyEmail(users, action_tokens, FakeUnitOfWork()).execute(emails.last_token)

    def test_concurrent_consume_loses(self, users, hasher, action_tokens, emails):
        user = add_user(users, hasher, verified=False)
        send_verification(users, action_tokens, emails).execute(user)
        token_id = next(iter(action_tokens.tokens))
        use_case = VerifyEmail(users, action_tokens, FakeUnitOfWork())
        action_tokens.consume = lambda *_: False

        with pytest.raises(InvalidVerificationLinkError):
            use_case.execute(emails.last_token)

        assert token_id in action_tokens.tokens
        assert users.get_by_id(user.id).email_verified_at is None


class TestResendEmailVerification:
    def resend(self, users, action_tokens, emails):
        return ResendEmailVerification(users, action_tokens, emails, FakeUnitOfWork(), BASE_URL)

    def test_sends_after_cooldown(self, users, hasher, action_tokens, emails):
        user = add_user(users, hasher, verified=False)
        send_verification(users, action_tokens, emails).execute(user)
        action_tokens.shift_all(-EMAIL_RESEND_COOLDOWN)

        self.resend(users, action_tokens, emails).execute(" BUDI@mail.com ")

        assert len(emails.sent) == 2

    def test_within_cooldown_is_silently_skipped(self, users, hasher, action_tokens, emails):
        user = add_user(users, hasher, verified=False)
        send_verification(users, action_tokens, emails).execute(user)

        self.resend(users, action_tokens, emails).execute("budi@mail.com")

        assert len(emails.sent) == 1

    def test_unknown_email_is_silently_skipped(self, users, action_tokens, emails):
        self.resend(users, action_tokens, emails).execute("tidakada@mail.com")

        assert emails.sent == []

    def test_verified_email_is_silently_skipped(self, users, hasher, action_tokens, emails):
        add_user(users, hasher)

        self.resend(users, action_tokens, emails).execute("budi@mail.com")

        assert emails.sent == []


class TestPasswordReset:
    def test_request_sends_link_valid_for_30_minutes(self, users, hasher, action_tokens, emails):
        add_user(users, hasher)

        request_reset(users, action_tokens, emails).execute("BUDI@mail.com")

        assert f"{BASE_URL}/auth/password/reset?token={emails.last_token}" in emails.sent[-1].text
        stored = next(iter(action_tokens.tokens.values()))
        assert stored.purpose == AuthActionPurpose.PASSWORD_RESET
        assert stored.expires_at - stored.created_at == timedelta(minutes=30)

    def test_unknown_email_is_silently_skipped(self, users, action_tokens, emails):
        request_reset(users, action_tokens, emails).execute("tidakada@mail.com")

        assert emails.sent == []
        assert action_tokens.tokens == {}

    def test_within_cooldown_keeps_first_link_valid(self, users, hasher, action_tokens, emails):
        user = add_user(users, hasher)
        request = request_reset(users, action_tokens, emails)
        request.execute("budi@mail.com")
        request.execute("budi@mail.com")

        assert len(emails.sent) == 1
        ResetPassword(users, action_tokens, hasher, FakeUnitOfWork()).execute(
            emails.last_token, "SandiBaru2024"
        )
        assert hasher.verify("SandiBaru2024", users.get_by_id(user.id).password_hash)

    def test_after_cooldown_old_link_stops_working(self, users, hasher, action_tokens, emails):
        add_user(users, hasher)
        request = request_reset(users, action_tokens, emails)
        request.execute("budi@mail.com")
        old_token = emails.last_token
        action_tokens.shift_all(-EMAIL_RESEND_COOLDOWN)
        request.execute("budi@mail.com")

        with pytest.raises(InvalidResetLinkError):
            ResetPassword(users, action_tokens, hasher, FakeUnitOfWork()).execute(
                old_token, "SandiBaru2024"
            )

    def test_reset_changes_password_and_commits(self, users, hasher, tokens, action_tokens, emails):
        user = add_user(users, hasher)
        request_reset(users, action_tokens, emails).execute("budi@mail.com")
        uow = FakeUnitOfWork()

        ResetPassword(users, action_tokens, hasher, uow).execute(emails.last_token, "SandiBaru2024")

        assert uow.committed
        saved = users.get_by_id(user.id)
        assert hasher.verify("SandiBaru2024", saved.password_hash)
        assert not hasher.verify(PASSWORD, saved.password_hash)
        assert saved.password_changed_at is not None

    def test_link_is_single_use(self, users, hasher, action_tokens, emails):
        user = add_user(users, hasher)
        request_reset(users, action_tokens, emails).execute("budi@mail.com")
        use_case = ResetPassword(users, action_tokens, hasher, FakeUnitOfWork())
        use_case.execute(emails.last_token, "SandiBaru2024")

        with pytest.raises(InvalidResetLinkError):
            use_case.execute(emails.last_token, "SandiLain2024")

        assert hasher.verify("SandiBaru2024", users.get_by_id(user.id).password_hash)

    def test_expired_link_keeps_old_password(self, users, hasher, action_tokens, emails):
        user = add_user(users, hasher)
        request_reset(users, action_tokens, emails).execute("budi@mail.com")
        action_tokens.shift_all(-PASSWORD_RESET_TTL)

        with pytest.raises(ExpiredResetLinkError):
            ResetPassword(users, action_tokens, hasher, FakeUnitOfWork()).execute(
                emails.last_token, "SandiBaru2024"
            )

        assert hasher.verify(PASSWORD, users.get_by_id(user.id).password_hash)

    def test_unknown_link(self, users, hasher, action_tokens):
        with pytest.raises(InvalidResetLinkError):
            ResetPassword(users, action_tokens, hasher, FakeUnitOfWork()).execute(
                "tidak-ada", "SandiBaru2024"
            )

    def test_verification_token_cannot_reset_password(self, users, hasher, action_tokens, emails):
        user = add_user(users, hasher, verified=False)
        send_verification(users, action_tokens, emails).execute(user)

        with pytest.raises(InvalidResetLinkError):
            ResetPassword(users, action_tokens, hasher, FakeUnitOfWork()).execute(
                emails.last_token, "SandiBaru2024"
            )

    def test_reset_verifies_unverified_email(self, users, hasher, action_tokens, emails):
        user = add_user(users, hasher, verified=False)
        request_reset(users, action_tokens, emails).execute("budi@mail.com")

        ResetPassword(users, action_tokens, hasher, FakeUnitOfWork()).execute(
            emails.last_token, "SandiBaru2024"
        )

        assert users.get_by_id(user.id).email_verified_at is not None

    def test_reset_ends_old_sessions_but_allows_new_login(
        self, users, hasher, tokens, revoked, action_tokens, emails
    ):
        user = add_user(users, hasher)
        old_session = tokens.create_access_token(user.id).token
        users.update_password(
            user.id, hasher.hash("SandiBaru2024"), datetime.now(UTC) + timedelta(seconds=2)
        )
        authenticate = AuthenticateToken(users, revoked, tokens)

        with pytest.raises(PasswordChangedError):
            authenticate.execute(old_session)

        users.update_password(user.id, hasher.hash("SandiBaru2024"), datetime.now(UTC))
        new_session = LoginUser(users, hasher, tokens).execute(
            LoginInput("budi@mail.com", "SandiBaru2024")
        )
        assert authenticate.execute(new_session.access_token.token).user.id == user.id


class TestLoginWithGoogle:
    TOKEN = "google-id-token"

    def use_case(self, users, hasher, tokens, email="budi@mail.com", email_verified=True, uow=None):
        google = FakeGoogleTokenVerifier()
        google.identities[self.TOKEN] = GoogleIdentity(email=email, email_verified=email_verified)
        return LoginWithGoogle(users, hasher, google, tokens, uow or FakeUnitOfWork())

    def test_registered_account_gets_token(self, users, hasher, tokens):
        user = add_user(users, hasher)

        result = self.use_case(users, hasher, tokens, email=" BUDI@Mail.com ").execute(self.TOKEN)

        assert result.user == user
        assert tokens.decode_access_token(result.access_token.token).user_id == user.id

    def test_verified_account_keeps_password(self, users, hasher, tokens):
        user = add_user(users, hasher)

        self.use_case(users, hasher, tokens).execute(self.TOKEN)

        assert hasher.verify(PASSWORD, users.get_by_id(user.id).password_hash)

    def test_unverified_account_is_claimed_and_password_replaced(self, users, hasher, tokens):
        user = add_user(users, hasher, verified=False)
        uow = FakeUnitOfWork()

        result = self.use_case(users, hasher, tokens, uow=uow).execute(self.TOKEN)

        assert uow.committed
        assert result.user.email_verified_at is not None
        assert not hasher.verify(PASSWORD, users.get_by_id(user.id).password_hash)

    def test_session_after_claim_is_valid(self, users, hasher, tokens, revoked):
        add_user(users, hasher, verified=False)

        result = self.use_case(users, hasher, tokens).execute(self.TOKEN)

        session = AuthenticateToken(users, revoked, tokens).execute(result.access_token.token)
        assert session.user.id == result.user.id

    def test_unregistered_email(self, users, hasher, tokens):
        with pytest.raises(GoogleAccountNotRegisteredError):
            self.use_case(users, hasher, tokens).execute(self.TOKEN)

    def test_google_email_not_verified(self, users, hasher, tokens):
        user = add_user(users, hasher, verified=False)

        with pytest.raises(GoogleEmailNotVerifiedError):
            self.use_case(users, hasher, tokens, email_verified=False).execute(self.TOKEN)

        assert hasher.verify(PASSWORD, users.get_by_id(user.id).password_hash)

    def test_admin_cannot_use_google_login(self, users, hasher, tokens):
        add_user(users, hasher, UserRole.ADMIN)

        with pytest.raises(PortalAccessDeniedError):
            self.use_case(users, hasher, tokens).execute(self.TOKEN)

    def test_invalid_token_propagates(self, users, hasher, tokens):
        with pytest.raises(InvalidGoogleTokenError):
            self.use_case(users, hasher, tokens).execute("token-lain")
