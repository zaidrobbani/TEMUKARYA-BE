import logging
from functools import lru_cache

import jwt
from fastapi import BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.email import EmailMessage, EmailSender, SmtpEmailSender
from app.core.google import GOOGLE_JWKS_URL, GoogleTokenVerifier, JwtGoogleTokenVerifier
from app.core.security import PasswordHasher, ScryptPasswordHasher
from app.core.tokens import JwtTokenService, TokenService
from app.core.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: Session):
        self._session = session

    def commit(self) -> None:
        self._session.commit()


def _send_safely(sender: EmailSender, message: EmailMessage) -> None:
    try:
        sender.send(message)
    except Exception:
        logger.exception("Gagal mengirim email: %s", message.subject)


class BackgroundEmailSender(EmailSender):
    """Kirim setelah response agar lama proses tidak membocorkan apakah email terdaftar."""

    def __init__(self, tasks: BackgroundTasks, sender: EmailSender):
        self._tasks = tasks
        self._sender = sender

    def send(self, message: EmailMessage) -> None:
        self._tasks.add_task(_send_safely, self._sender, message)


def get_email_sender(background_tasks: BackgroundTasks) -> EmailSender:
    smtp = SmtpEmailSender(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        sender=settings.EMAIL_FROM,
        username=settings.SMTP_USERNAME,
        password=settings.SMTP_PASSWORD,
        use_tls=settings.SMTP_USE_TLS,
    )
    return BackgroundEmailSender(background_tasks, smtp)


@lru_cache
def _google_jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(GOOGLE_JWKS_URL, timeout=5)


def get_google_token_verifier() -> GoogleTokenVerifier:
    return JwtGoogleTokenVerifier(settings.GOOGLE_CLIENT_ID, _google_jwks_client())


def get_uow(db: Session = Depends(get_db)) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(db)


def get_password_hasher() -> PasswordHasher:
    return ScryptPasswordHasher()


def get_token_service() -> TokenService:
    return JwtTokenService(
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expire_minutes=settings.JWT_EXPIRE_MINUTES,
    )
