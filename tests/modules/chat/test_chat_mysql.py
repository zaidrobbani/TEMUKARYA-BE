import os

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import bindparam, inspect, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import NotFoundError

from app.modules.chat.application.dto import (
    CreateConversationInput,
    GetConversationInput,
    ListConversationsInput,
    ListMessagesInput,
    MarkConversationReadInput,
    SendTextMessageInput,
)

from app.modules.chat.application.use_cases import (
    CreateOrGetConversation,
    GetConversation,
    ListConversationMessages,
    ListUserConversations,
    MarkConversationRead,
    SendTextMessage,
)

from app.modules.chat.domain.entities import (
    ChatActor,
    Message,
    MessageAttachment,
    MessageType,
)

from app.modules.chat.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)


# ============================================================
# 1. TEST CONSTANTS
# ============================================================

NOW = datetime(
    2026, 11, 4, 10, 0,
    tzinfo=timezone.utc,
)


# ============================================================
# 2. MYSQL SAFETY GUARD
# ============================================================

def require_safe_mysql():

    if os.getenv("TEMUKARYA_RUN_MYSQL_TESTS") != "1":
        pytest.skip(
            "MySQL integration test belum diaktifkan"
        )

    if engine.url.get_backend_name() != "mysql":
        pytest.fail("Test membutuhkan MySQL")

    if engine.url.host not in {
        "localhost",
        "127.0.0.1",
    }:
        pytest.fail(
            "Hanya database MySQL lokal "
            "yang diizinkan"
        )

    if engine.url.database != "temukarya":
        pytest.fail(
            "Database harus bernama temukarya"
        )

    if str(settings.APP_ENV).lower() in {
        "production",
        "prod",
    }:
        pytest.fail(
            "Dilarang menjalankan integration test "
            "pada production"
        )

    inspector = inspect(engine)

    required = {
        "users",
        "umkm_profiles",
        "freelancer_profiles",
        "project_categories",
        "projects",
        "conversations",
        "messages",
        "message_attachments",
    }

    missing = required - set(
        inspector.get_table_names()
    )

    if missing:
        pytest.fail(
            "Tabel database belum lengkap: "
            + ", ".join(sorted(missing))
        )

    print("\nMYSQL CHAT TABLE CONTRACT: OK")


# ============================================================
# 3. SQL INSERT HELPER
# ============================================================

def insert_data(
    session: Session,
    query: str,
    parameters,
) -> None:

    session.execute(
        text(query),
        parameters,
    )


# ============================================================
# 4. MYSQL INTEGRATION TEST
# ============================================================

def test_chat_mysql_integration_and_rollback():

    # ========================================================
    # A. CHECK DATABASE SAFETY
    # ========================================================

    require_safe_mysql()

    # ========================================================
    # B. GENERATE TEMPORARY IDS
    # ========================================================

    tag = uuid4().hex[:12]

    umkm_id = str(uuid4())
    freelancer_id = str(uuid4())
    outsider_id = str(uuid4())

    project_id = str(uuid4())
    category_id = f"chat-cat-{tag}"

    actor_umkm = ChatActor(
        user_id=umkm_id,
        role="UMKM",
    )

    actor_freelancer = ChatActor(
        user_id=freelancer_id,
        role="FREELANCER",
    )

    actor_outsider = ChatActor(
        user_id=outsider_id,
        role="UMKM",
    )

    # IDs untuk validasi rollback.
    created_conversations = []
    created_messages = []
    created_attachments = []

    # ========================================================
    # C. BEGIN OUTER TRANSACTION
    # ========================================================

    with engine.connect() as connection:

        transaction = connection.begin()

        try:

            with Session(
                bind=connection,
                autoflush=False,
                expire_on_commit=False,
            ) as session:

                # ============================================
                # 1. CREATE TEMPORARY USERS
                # ============================================

                insert_data(
                    session,
                    """
                    INSERT INTO users (
                        id,
                        name,
                        email,
                        password_hash,
                        role
                    )
                    VALUES (
                        :id,
                        :name,
                        :email,
                        :password_hash,
                        :role
                    )
                    """,
                    [
                        {
                            "id": umkm_id,
                            "name": "Chat Test UMKM",
                            "email": (
                                f"chat-umkm-{tag}@example.invalid"
                            ),
                            "password_hash": "test-only-hash",
                            "role": "UMKM",
                        },
                        {
                            "id": freelancer_id,
                            "name": "Chat Test Freelancer",
                            "email": (
                                f"chat-freelancer-{tag}@example.invalid"
                            ),
                            "password_hash": "test-only-hash",
                            "role": "FREELANCER",
                        },
                        {
                            "id": outsider_id,
                            "name": "Chat Test Outsider",
                            "email": (
                                f"chat-outsider-{tag}@example.invalid"
                            ),
                            "password_hash": "test-only-hash",
                            "role": "UMKM",
                        },
                    ],
                )

                # ============================================
                # 2. CREATE UMKM PROFILE
                # ============================================

                insert_data(
                    session,
                    """
                    INSERT INTO umkm_profiles (
                        user_id,
                        business_name,
                        business_category,
                        business_address,
                        city
                    )
                    VALUES (
                        :user_id,
                        :business_name,
                        'Technology',
                        'Temporary Test Address',
                        'Malang'
                    )
                    """,
                    {
                        "user_id": umkm_id,
                        "business_name": (
                            f"Chat UMKM {tag}"
                        ),
                    },
                )

                # ============================================
                # 3. CREATE FREELANCER PROFILE
                # ============================================

                insert_data(
                    session,
                    """
                    INSERT INTO freelancer_profiles (
                        user_id,
                        professional_title,
                        bio,
                        city,
                        availability_status
                    )
                    VALUES (
                        :user_id,
                        'Software Developer',
                        'Temporary chat test',
                        'Malang',
                        'AVAILABLE'
                    )
                    """,
                    {
                        "user_id": freelancer_id,
                    },
                )

                # ============================================
                # 4. CREATE PROJECT CATEGORY
                # ============================================

                insert_data(
                    session,
                    """
                    INSERT INTO project_categories (
                        id,
                        name,
                        description,
                        is_active
                    )
                    VALUES (
                        :id,
                        :name,
                        'Temporary chat category',
                        1
                    )
                    """,
                    {
                        "id": category_id,
                        "name": (
                            f"Chat Category {tag}"
                        ),
                    },
                )

                # ============================================
                # 5. CREATE TEMPORARY PROJECT
                # ============================================

                insert_data(
                    session,
                    """
                    INSERT INTO projects (
                        id,
                        umkm_id,
                        category_id,
                        title,
                        description,
                        budget,
                        deadline,
                        status,
                        published_at
                    )
                    VALUES (
                        :id,
                        :umkm_id,
                        :category_id,
                        :title,
                        'Temporary Chat Project',
                        2000000,
                        :deadline,
                        'TERBUKA',
                        :published_at
                    )
                    """,
                    {
                        "id": project_id,
                        "umkm_id": umkm_id,
                        "category_id": category_id,
                        "title": f"Chat Project {tag}",
                        "deadline": date(
                            2026, 11, 20
                        ),
                        "published_at": NOW.replace(
                            tzinfo=None
                        ),
                    },
                )

                print("MYSQL TEMPORARY USERS/PROJECT: OK")

                # ============================================
                # 6. INITIALIZE REAL REPOSITORIES
                # ============================================

                conversation_repo = (
                    SqlAlchemyConversationRepository(
                        session
                    )
                )

                message_repo = (
                    SqlAlchemyMessageRepository(
                        session
                    )
                )

                # ============================================
                # 7. TEST GENERAL CONVERSATION
                # ============================================

                create_conversation = (
                    CreateOrGetConversation(
                        conversation_repo,
                        clock=lambda: NOW,
                    )
                )

                general = create_conversation.execute(
                    CreateConversationInput(
                        actor=actor_umkm,
                        counterpart_user_id=freelancer_id,
                    )
                )

                created_conversations.append(
                    general.id
                )

                assert general.project_id is None
                assert general.umkm_id == umkm_id
                assert general.freelancer_id == (
                    freelancer_id
                )

                print(
                    "MYSQL GENERAL CONVERSATION: OK"
                )

                # ============================================
                # 8. TEST DUPLICATE CONVERSATION
                # ============================================

                duplicate = create_conversation.execute(
                    CreateConversationInput(
                        actor=actor_freelancer,
                        counterpart_user_id=umkm_id,
                    )
                )

                assert duplicate.id == general.id

                # Paksa jalur UPSERT database.
                # ID lain untuk pasangan yang sama.
                database_duplicate = (
                    conversation_repo.create_or_get(
                        replace(
                            general,
                            id=str(uuid4()),
                        )
                    )
                )

                assert database_duplicate.id == (
                    general.id
                )

                count = session.execute(
                    text("""
                        SELECT COUNT(*)
                        FROM conversations
                        WHERE umkm_id = :umkm_id
                        AND freelancer_id = :freelancer_id
                        AND project_id IS NULL
                    """),
                    {
                        "umkm_id": umkm_id,
                        "freelancer_id": freelancer_id,
                    },
                ).scalar_one()

                assert count == 1

                print(
                    "MYSQL DUPLICATE PREVENTION: OK"
                )

                # ============================================
                # 9. TEST PROJECT CONVERSATION
                # ============================================

                project_chat = (
                    create_conversation.execute(
                        CreateConversationInput(
                            actor=actor_umkm,
                            counterpart_user_id=(
                                freelancer_id
                            ),
                            project_id=project_id,
                        )
                    )
                )

                created_conversations.append(
                    project_chat.id
                )

                assert project_chat.project_id == (
                    project_id
                )

                assert project_chat.id != general.id

                print(
                    "MYSQL PROJECT CONVERSATION: OK"
                )

                # ============================================
                # 10. TEST CONVERSATION ACCESS
                # ============================================

                get_conversation = GetConversation(
                    conversation_repo
                )

                assert get_conversation.execute(
                    GetConversationInput(
                        conversation_id=general.id,
                        actor=actor_umkm,
                    )
                ).id == general.id

                assert get_conversation.execute(
                    GetConversationInput(
                        conversation_id=general.id,
                        actor=actor_freelancer,
                    )
                ).id == general.id

                with pytest.raises(NotFoundError):
                    get_conversation.execute(
                        GetConversationInput(
                            conversation_id=general.id,
                            actor=actor_outsider,
                        )
                    )

                print(
                    "MYSQL CONVERSATION OWNERSHIP: OK"
                )

                # ============================================
                # 11. TEST CONVERSATION LIST
                # ============================================

                conversations = (
                    ListUserConversations(
                        conversation_repo
                    ).execute(
                        ListConversationsInput(
                            actor=actor_umkm,
                            limit=10,
                        )
                    )
                )

                assert len(conversations.items) == 2

                outsider_list = (
                    ListUserConversations(
                        conversation_repo
                    ).execute(
                        ListConversationsInput(
                            actor=actor_outsider,
                        )
                    )
                )

                assert outsider_list.items == ()

                print(
                    "MYSQL PRIVATE CONVERSATION LIST: OK"
                )

                # ============================================
                # 12. SEND TEXT FROM UMKM
                # ============================================

                send_umkm = SendTextMessage(
                    conversation_repo,
                    message_repo,
                    clock=lambda: (
                        NOW + timedelta(minutes=1)
                    ),
                )

                first = send_umkm.execute(
                    SendTextMessageInput(
                        conversation_id=general.id,
                        actor=actor_umkm,
                        message_text="  Halo Freelancer! ",
                    )
                )

                created_messages.append(
                    first.id
                )

                assert first.sender_user_id == umkm_id
                assert first.message_text == (
                    "Halo Freelancer!"
                )

                # ============================================
                # 13. SEND REPLY FROM FREELANCER
                # ============================================

                send_freelancer = SendTextMessage(
                    conversation_repo,
                    message_repo,
                    clock=lambda: (
                        NOW + timedelta(minutes=2)
                    ),
                )

                second = send_freelancer.execute(
                    SendTextMessageInput(
                        conversation_id=general.id,
                        actor=actor_freelancer,
                        message_text="Siap, Kak!",
                    )
                )

                created_messages.append(
                    second.id
                )

                assert second.sender_user_id == (
                    freelancer_id
                )

                # ============================================
                # 14. VERIFY LAST MESSAGE TIMESTAMP
                # ============================================

                updated_conversation = (
                    conversation_repo.get_by_id(
                        general.id
                    )
                )

                assert (
                    updated_conversation.last_message_at
                    == second.sent_at
                )

                print(
                    "MYSQL MESSAGE SEND + TIMESTAMP: OK"
                )

                # ============================================
                # 15. TEST MESSAGE HISTORY
                # ============================================

                get_messages = ListConversationMessages(
                    conversation_repo,
                    message_repo,
                )

                history = get_messages.execute(
                    ListMessagesInput(
                        conversation_id=general.id,
                        actor=actor_umkm,
                        limit=10,
                    )
                )

                assert [
                    item.message.id
                    for item in history.items
                ] == [
                    second.id,
                    first.id,
                ]

                # ============================================
                # 16. TEST KEYSET PAGINATION
                # ============================================

                page_one = get_messages.execute(
                    ListMessagesInput(
                        conversation_id=general.id,
                        actor=actor_umkm,
                        limit=1,
                    )
                )

                assert page_one.has_more is True
                assert page_one.next_before is not None

                page_two = get_messages.execute(
                    ListMessagesInput(
                        conversation_id=general.id,
                        actor=actor_umkm,
                        limit=1,
                        before=page_one.next_before,
                    )
                )

                assert page_two.has_more is False

                assert page_one.items[0].message.id == (
                    second.id
                )

                assert page_two.items[0].message.id == (
                    first.id
                )

                print(
                    "MYSQL MESSAGE HISTORY + PAGINATION: OK"
                )

                # ============================================
                # 17. TEST MARK AS READ
                # ============================================

                mark_read = MarkConversationRead(
                    conversation_repo,
                    message_repo,
                    clock=lambda: (
                        NOW + timedelta(minutes=3)
                    ),
                )

                read_result = mark_read.execute(
                    MarkConversationReadInput(
                        conversation_id=general.id,
                        actor=actor_umkm,
                    )
                )

                assert read_result.marked_count == 1

                assert message_repo.get_by_id(
                    first.id
                ).read_at is None

                assert message_repo.get_by_id(
                    second.id
                ).read_at is not None

                # ============================================
                # 18. TEST IDEMPOTENT MARK AS READ
                # ============================================

                read_again = mark_read.execute(
                    MarkConversationReadInput(
                        conversation_id=general.id,
                        actor=actor_umkm,
                    )
                )

                assert read_again.marked_count == 0

                print(
                    "MYSQL MESSAGE READ + IDEMPOTENCY: OK"
                )

                # ============================================
                # 19. TEST FILE ATTACHMENT METADATA
                # ============================================

                file_message = Message(
                    id=str(uuid4()),
                    conversation_id=general.id,
                    sender_user_id=umkm_id,
                    message_text=None,
                    message_type=MessageType.FILE,
                    sent_at=NOW + timedelta(minutes=4),
                    created_at=NOW + timedelta(minutes=4),
                )

                attachment = MessageAttachment(
                    id=str(uuid4()),
                    message_id=file_message.id,
                    original_file_name="brief.pdf",
                    storage_key=(
                        f"chat/{file_message.id}/brief.pdf"
                    ),
                    mime_type="application/pdf",
                    file_size_bytes=2048,
                    uploaded_at=NOW + timedelta(minutes=4),
                )

                message_repo.create_with_attachments(
                    message=file_message,
                    attachments=(attachment,),
                )

                created_messages.append(
                    file_message.id
                )

                created_attachments.append(
                    attachment.id
                )

                fetched_attachments = (
                    message_repo.list_attachments(
                        (file_message.id,)
                    )
                )

                assert len(fetched_attachments) == 1

                assert fetched_attachments[0].storage_key == (
                    attachment.storage_key
                )

                assert fetched_attachments[0].mime_type == (
                    "application/pdf"
                )

                print(
                    "MYSQL ATTACHMENT METADATA: OK"
                )

                # ============================================
                # 20. TEST FORGED SENDER REJECTED
                # ============================================

                forged = Message(
                    id=str(uuid4()),
                    conversation_id=general.id,
                    sender_user_id=outsider_id,
                    message_text="Forged message",
                    message_type=MessageType.TEXT,
                    sent_at=NOW + timedelta(minutes=5),
                    created_at=NOW + timedelta(minutes=5),
                )

                with pytest.raises(NotFoundError):
                    message_repo.create_with_attachments(
                        forged,
                        (),
                    )

                assert message_repo.get_by_id(
                    forged.id
                ) is None

                print(
                    "MYSQL FORGED SENDER PROTECTION: OK"
                )

                # ============================================
                # 21. VERIFY DATA COUNTS
                # ============================================

                count_messages = session.execute(
                    text("""
                        SELECT COUNT(*)
                        FROM messages
                        WHERE conversation_id = :conversation_id
                    """),
                    {
                        "conversation_id": general.id,
                    },
                ).scalar_one()

                assert count_messages == 3

                print(
                    "MYSQL MESSAGE DATA INTEGRITY: OK"
                )

        finally:

            # ================================================
            # 22. ALWAYS ROLLBACK
            # ================================================

            if transaction.is_active:
                transaction.rollback()

            print(
                "MYSQL TRANSACTION ROLLBACK: OK"
            )

    # ========================================================
    # D. VERIFY NO TEST DATA WAS LEFT
    # ========================================================

    checks = [
        (
            "users",
            "id",
            [umkm_id, freelancer_id, outsider_id],
        ),
        (
            "umkm_profiles",
            "user_id",
            [umkm_id],
        ),
        (
            "freelancer_profiles",
            "user_id",
            [freelancer_id],
        ),
        (
            "project_categories",
            "id",
            [category_id],
        ),
        (
            "projects",
            "id",
            [project_id],
        ),
        (
            "conversations",
            "id",
            created_conversations,
        ),
        (
            "messages",
            "id",
            created_messages,
        ),
        (
            "message_attachments",
            "id",
            created_attachments,
        ),
    ]

    with engine.connect() as check_connection:

        for table, column, ids in checks:

            if not ids:
                continue

            statement = text(
                f"SELECT COUNT(*) "
                f"FROM {table} "
                f"WHERE {column} IN :ids"
            ).bindparams(
                bindparam(
                    "ids",
                    expanding=True,
                )
            )

            remaining = check_connection.execute(
                statement,
                {
                    "ids": ids,
                },
            ).scalar_one()

            assert remaining == 0, (
                f"Data sementara masih ada di {table}"
            )

    print("MYSQL DATABASE CLEANUP: OK")
    print("MYSQL CHAT INTEGRATION: PASSED")