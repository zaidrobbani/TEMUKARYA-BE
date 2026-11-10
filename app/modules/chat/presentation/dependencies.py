from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.presentation.dependencies import get_current_user
from app.modules.chat.domain.entities import ChatActor

from app.modules.chat.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from app.modules.notifications.infrastructure.hooks import notify_new_message
from app.modules.users.domain.entities import User


# 1. CHAT ACTOR (dari JWT)

def get_authenticated_chat_actor(
    user: Annotated[User, Depends(get_current_user)],
) -> ChatActor:
    return ChatActor(user_id=user.id, role=user.role)


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


# 4. NOTIFIKASI PESAN BARU (ikut transaksi pengiriman pesan)

NewMessageHook = Callable[[str, str, str], None]


def get_new_message_hook(
    db: Annotated[
        ChatDatabaseContext,
        Depends(get_chat_database_context),
    ],
) -> NewMessageHook:
    def hook(conversation_id: str, sender_id: str, message_text: str) -> None:
        notify_new_message(db.session, conversation_id, sender_id, message_text)

    return hook
