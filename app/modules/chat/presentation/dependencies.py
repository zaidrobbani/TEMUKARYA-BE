from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError

from app.modules.chat.domain.entities import ChatActor

from app.modules.chat.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)


# 1. CHAT ACTOR - FAIL CLOSED

def get_authenticated_chat_actor() -> ChatActor:
    """
    Identitas pengguna harus berasal dari JWT.

    Sampai Auth Module milik Zaid terintegrasi,
    semua request ditolak dengan 401.

    Jangan menerima user_id atau role
    langsung dari body/header buatan client.
    """

    raise UnauthorizedError(
        "Autentikasi Chat belum "
        "terintegrasi dengan JWT"
    )


# 2. CHAT DATABASE CONTEXT

@dataclass(slots=True)
class ChatDatabaseContext:
    """
    Kedua Repository memakai SQLAlchemy
    Session yang sama.

    Ini diperlukan agar proses:
      - membuat conversation
      - menyimpan message
      - memperbarui last_message_at
      - memperbarui read_at

    menggunakan transaksi yang konsisten.
    """

    session: Session

    conversations: SqlAlchemyConversationRepository
    messages: SqlAlchemyMessageRepository


# 3. CONTEXT DEPENDENCY

def get_chat_database_context(
    session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> ChatDatabaseContext:

    return ChatDatabaseContext(
        session=session,
        conversations=SqlAlchemyConversationRepository(
            session
        ),
        messages=SqlAlchemyMessageRepository(
            session
        ),
    )