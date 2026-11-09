import secrets
from datetime import UTC, datetime, timedelta

from app.core.email import EmailSender
from app.core.google import GoogleTokenVerifier
from app.core.security import PasswordHasher
from app.core.tokens import TokenService
from app.core.unit_of_work import UnitOfWork
from app.modules.auth.application.dto import LoginInput, LoginResult
from app.modules.auth.application.emails import email_verification_message, password_reset_message
from app.modules.auth.domain.entities import (
    EMAIL_RESEND_COOLDOWN,
    EMAIL_VERIFICATION_TTL,
    PASSWORD_RESET_TTL,
    PORTAL_ROLES,
    AuthActionPurpose,
    AuthActionToken,
    AuthSession,
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
from app.modules.auth.domain.repositories import AuthActionTokenRepository, RevokedTokenRepository
from app.modules.users.application.dto import RegisterUserInput
from app.modules.users.application.use_cases import RegisterUser
from app.modules.users.domain.entities import User
from app.modules.users.domain.repositories import UserRepository


class LoginUser:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, tokens: TokenService):
        self._users = users
        self._hasher = hasher
        self._tokens = tokens

    def execute(self, data: LoginInput) -> LoginResult:
        user = self._users.get_by_email(data.email.strip().lower())
        if user is None or not self._hasher.verify(data.password, user.password_hash):
            raise InvalidCredentialsError()

        if user.role not in PORTAL_ROLES[data.portal]:
            raise PortalAccessDeniedError(data.portal)

        if user.email_verified_at is None:
            raise EmailNotVerifiedError()

        return LoginResult(user=user, access_token=self._tokens.create_access_token(user.id))


class LoginWithGoogle:
    def __init__(
        self,
        users: UserRepository,
        hasher: PasswordHasher,
        google: GoogleTokenVerifier,
        tokens: TokenService,
        uow: UnitOfWork,
    ):
        self._users = users
        self._hasher = hasher
        self._google = google
        self._tokens = tokens
        self._uow = uow

    def execute(self, id_token: str) -> LoginResult:
        identity = self._google.verify(id_token)
        if not identity.email_verified:
            raise GoogleEmailNotVerifiedError()

        user = self._users.get_by_email(identity.email.strip().lower())
        if user is None:
            raise GoogleAccountNotRegisteredError()
        if user.role not in PORTAL_ROLES[LoginPortal.MOBILE_APP]:
            raise PortalAccessDeniedError(LoginPortal.MOBILE_APP)

        if user.email_verified_at is None:
            user = self._claim_unverified_account(user)

        return LoginResult(user=user, access_token=self._tokens.create_access_token(user.id))

    def _claim_unverified_account(self, user: User) -> User:
        now = datetime.now(UTC)
        self._users.update_password(user.id, self._hasher.hash(secrets.token_urlsafe(32)), now)
        self._users.mark_email_verified(user.id, now)
        self._uow.commit()
        return self._users.get_by_id(user.id)


class AuthenticateToken:
    def __init__(
        self,
        users: UserRepository,
        revoked_tokens: RevokedTokenRepository,
        tokens: TokenService,
    ):
        self._users = users
        self._revoked_tokens = revoked_tokens
        self._tokens = tokens

    def execute(self, token: str) -> AuthSession:
        claims = self._tokens.decode_access_token(token)
        if self._revoked_tokens.exists(claims.jti):
            raise SessionRevokedError()

        user = self._users.get_by_id(claims.user_id)
        if user is None:
            raise AccountNotFoundError()

        if user.password_changed_at and claims.issued_at < user.password_changed_at.replace(microsecond=0):
            raise PasswordChangedError()
        return AuthSession(user=user, claims=claims)


class LogoutUser:
    def __init__(self, revoked_tokens: RevokedTokenRepository, uow: UnitOfWork):
        self._revoked_tokens = revoked_tokens
        self._uow = uow

    def execute(self, session: AuthSession) -> None:
        self._revoked_tokens.add(
            jti=session.claims.jti,
            user_id=session.user.id,
            expires_at=session.claims.expires_at,
        )
        self._uow.commit()


class _ActionLinkSender:
    def __init__(
        self,
        users: UserRepository,
        action_tokens: AuthActionTokenRepository,
        email_sender: EmailSender,
        uow: UnitOfWork,
        public_base_url: str,
    ):
        self._users = users
        self._action_tokens = action_tokens
        self._email_sender = email_sender
        self._uow = uow
        self._public_base_url = public_base_url.rstrip("/")

    def _is_cooling_down(self, user_id: str, purpose: AuthActionPurpose, now: datetime) -> bool:
        latest = self._action_tokens.latest_created_at(user_id, purpose)
        return latest is not None and now - latest < EMAIL_RESEND_COOLDOWN

    def _create_link(
        self,
        user_id: str,
        purpose: AuthActionPurpose,
        ttl: timedelta,
        path: str,
        now: datetime,
    ) -> str:
        raw_token = secrets.token_urlsafe(32)
        self._action_tokens.invalidate_active(user_id, purpose, now)
        self._action_tokens.add(
            AuthActionToken(
                user_id=user_id,
                purpose=purpose,
                token_hash=hash_action_token(raw_token),
                expires_at=now + ttl,
                created_at=now,
            )
        )
        self._uow.commit()
        return f"{self._public_base_url}{path}?token={raw_token}"

    def _send_verification(self, user: User, now: datetime) -> None:
        link = self._create_link(
            user.id,
            AuthActionPurpose.EMAIL_VERIFICATION,
            EMAIL_VERIFICATION_TTL,
            "/auth/email/verify",
            now,
        )
        self._email_sender.send(email_verification_message(user, link))


class SendEmailVerification(_ActionLinkSender):
    def execute(self, user: User) -> None:
        self._send_verification(user, datetime.now(UTC))


class ResendEmailVerification(_ActionLinkSender):
    def execute(self, email: str) -> None:
        user = self._users.get_by_email(email.strip().lower())
        if user is None or user.email_verified_at is not None:
            return
        now = datetime.now(UTC)
        if self._is_cooling_down(user.id, AuthActionPurpose.EMAIL_VERIFICATION, now):
            return
        self._send_verification(user, now)


class RequestPasswordReset(_ActionLinkSender):
    def execute(self, email: str) -> None:
        user = self._users.get_by_email(email.strip().lower())
        if user is None:
            return
        now = datetime.now(UTC)
        if self._is_cooling_down(user.id, AuthActionPurpose.PASSWORD_RESET, now):
            return
        link = self._create_link(
            user.id,
            AuthActionPurpose.PASSWORD_RESET,
            PASSWORD_RESET_TTL,
            "/auth/password/reset",
            now,
        )
        self._email_sender.send(password_reset_message(user, link))


class RegisterAccount:
    def __init__(self, register_user: RegisterUser, send_verification: SendEmailVerification):
        self._register_user = register_user
        self._send_verification = send_verification

    def execute(self, data: RegisterUserInput) -> User:
        user = self._register_user.execute(data)
        self._send_verification.execute(user)
        return user


class VerifyEmail:
    def __init__(
        self,
        users: UserRepository,
        action_tokens: AuthActionTokenRepository,
        uow: UnitOfWork,
    ):
        self._users = users
        self._action_tokens = action_tokens
        self._uow = uow

    def execute(self, raw_token: str) -> None:
        token = self._action_tokens.get_by_hash(
            hash_action_token(raw_token), AuthActionPurpose.EMAIL_VERIFICATION
        )
        user = self._users.get_by_id(token.user_id) if token else None
        if user is None:
            raise InvalidVerificationLinkError()

        if user.email_verified_at is not None:
            return

        now = datetime.now(UTC)
        if token.used_at is not None:
            raise InvalidVerificationLinkError()
        if token.is_expired(now):
            raise ExpiredVerificationLinkError()
        if not self._action_tokens.consume(token.id, now):
            raise InvalidVerificationLinkError()

        self._users.mark_email_verified(user.id, now)
        self._uow.commit()


class ResetPassword:
    def __init__(
        self,
        users: UserRepository,
        action_tokens: AuthActionTokenRepository,
        hasher: PasswordHasher,
        uow: UnitOfWork,
    ):
        self._users = users
        self._action_tokens = action_tokens
        self._hasher = hasher
        self._uow = uow

    def execute(self, raw_token: str, new_password: str) -> None:
        token = self._action_tokens.get_by_hash(
            hash_action_token(raw_token), AuthActionPurpose.PASSWORD_RESET
        )
        user = self._users.get_by_id(token.user_id) if token else None
        if user is None or token.used_at is not None:
            raise InvalidResetLinkError()

        now = datetime.now(UTC)
        if token.is_expired(now):
            raise ExpiredResetLinkError()

        password_hash = self._hasher.hash(new_password)
        if not self._action_tokens.consume(token.id, now):
            raise InvalidResetLinkError()

        self._users.update_password(user.id, password_hash, now)
        if user.email_verified_at is None:
            self._users.mark_email_verified(user.id, now)
        self._uow.commit()
