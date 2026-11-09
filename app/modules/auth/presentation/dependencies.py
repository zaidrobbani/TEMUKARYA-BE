from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import (
    get_email_sender,
    get_google_token_verifier,
    get_password_hasher,
    get_token_service,
    get_uow,
)
from app.core.email import EmailSender
from app.core.google import GoogleTokenVerifier
from app.core.security import PasswordHasher
from app.core.tokens import TokenService
from app.core.unit_of_work import UnitOfWork
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
from app.modules.auth.domain.entities import AuthSession
from app.modules.auth.domain.exceptions import InsufficientRoleError, NotAuthenticatedError
from app.modules.auth.domain.repositories import AuthActionTokenRepository, RevokedTokenRepository
from app.modules.auth.infrastructure.repositories import (
    SqlAlchemyAuthActionTokenRepository,
    SqlAlchemyRevokedTokenRepository,
)
from app.modules.users.application.use_cases import RegisterUser
from app.modules.users.domain.entities import User, UserRole
from app.modules.users.domain.repositories import UserRepository
from app.modules.users.presentation.dependencies import get_user_repository, register_user_use_case

bearer_scheme = HTTPBearer(auto_error=False, description="Access token dari /api/v1/auth/login")


def get_revoked_token_repository(db: Session = Depends(get_db)) -> RevokedTokenRepository:
    return SqlAlchemyRevokedTokenRepository(db)


def get_action_token_repository(db: Session = Depends(get_db)) -> AuthActionTokenRepository:
    return SqlAlchemyAuthActionTokenRepository(db)


def google_login_use_case(
    users: UserRepository = Depends(get_user_repository),
    hasher: PasswordHasher = Depends(get_password_hasher),
    google: GoogleTokenVerifier = Depends(get_google_token_verifier),
    tokens: TokenService = Depends(get_token_service),
    uow: UnitOfWork = Depends(get_uow),
) -> LoginWithGoogle:
    return LoginWithGoogle(users, hasher, google, tokens, uow)


def send_email_verification_use_case(
    users: UserRepository = Depends(get_user_repository),
    action_tokens: AuthActionTokenRepository = Depends(get_action_token_repository),
    email_sender: EmailSender = Depends(get_email_sender),
    uow: UnitOfWork = Depends(get_uow),
) -> SendEmailVerification:
    return SendEmailVerification(users, action_tokens, email_sender, uow, settings.PUBLIC_API_URL)


def register_account_use_case(
    register_user: RegisterUser = Depends(register_user_use_case),
    send_verification: SendEmailVerification = Depends(send_email_verification_use_case),
) -> RegisterAccount:
    return RegisterAccount(register_user, send_verification)


def resend_email_verification_use_case(
    users: UserRepository = Depends(get_user_repository),
    action_tokens: AuthActionTokenRepository = Depends(get_action_token_repository),
    email_sender: EmailSender = Depends(get_email_sender),
    uow: UnitOfWork = Depends(get_uow),
) -> ResendEmailVerification:
    return ResendEmailVerification(users, action_tokens, email_sender, uow, settings.PUBLIC_API_URL)


def request_password_reset_use_case(
    users: UserRepository = Depends(get_user_repository),
    action_tokens: AuthActionTokenRepository = Depends(get_action_token_repository),
    email_sender: EmailSender = Depends(get_email_sender),
    uow: UnitOfWork = Depends(get_uow),
) -> RequestPasswordReset:
    return RequestPasswordReset(users, action_tokens, email_sender, uow, settings.PUBLIC_API_URL)


def verify_email_use_case(
    users: UserRepository = Depends(get_user_repository),
    action_tokens: AuthActionTokenRepository = Depends(get_action_token_repository),
    uow: UnitOfWork = Depends(get_uow),
) -> VerifyEmail:
    return VerifyEmail(users, action_tokens, uow)


def reset_password_use_case(
    users: UserRepository = Depends(get_user_repository),
    action_tokens: AuthActionTokenRepository = Depends(get_action_token_repository),
    hasher: PasswordHasher = Depends(get_password_hasher),
    uow: UnitOfWork = Depends(get_uow),
) -> ResetPassword:
    return ResetPassword(users, action_tokens, hasher, uow)


def login_use_case(
    users: UserRepository = Depends(get_user_repository),
    hasher: PasswordHasher = Depends(get_password_hasher),
    tokens: TokenService = Depends(get_token_service),
) -> LoginUser:
    return LoginUser(users, hasher, tokens)


def authenticate_token_use_case(
    users: UserRepository = Depends(get_user_repository),
    revoked_tokens: RevokedTokenRepository = Depends(get_revoked_token_repository),
    tokens: TokenService = Depends(get_token_service),
) -> AuthenticateToken:
    return AuthenticateToken(users, revoked_tokens, tokens)


def logout_use_case(
    revoked_tokens: RevokedTokenRepository = Depends(get_revoked_token_repository),
    uow: UnitOfWork = Depends(get_uow),
) -> LogoutUser:
    return LogoutUser(revoked_tokens, uow)


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    use_case: AuthenticateToken = Depends(authenticate_token_use_case),
) -> AuthSession:
    if credentials is None:
        raise NotAuthenticatedError()
    return use_case.execute(credentials.credentials)


def get_current_user(session: AuthSession = Depends(get_current_session)) -> User:
    return session.user


def require_roles(*roles: UserRole) -> Callable[..., User]:
    allowed = frozenset(roles)

    def ensure_role(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise InsufficientRoleError()
        return user

    return ensure_role
