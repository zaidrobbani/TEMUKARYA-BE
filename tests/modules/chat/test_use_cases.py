from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)

from app.modules.chat.application.dto import (
    CreateConversationInput,
    GetConversationInput,
    ListConversationsInput,
    SendTextMessageInput,
    ListMessagesInput,
    MarkConversationReadInput,
)

from app.modules.chat.application.use_cases import (
    CreateOrGetConversation,
    GetConversation,
    ListUserConversations,
    SendTextMessage,
    ListConversationMessages,
    MarkConversationRead,
)

from app.modules.chat.domain.entities import (
    ChatActor,
    Conversation,
    Message,
    MessageAttachment,
    MessageType,
)


# ============================================================
# 1. TEST CONSTANTS
# ============================================================

NOW = datetime(
    2026, 11, 4, 10, 0,
    tzinfo=timezone.utc,
)

UMKM = ChatActor("u1", "umkm")
FREELANCER = ChatActor("f1", "freelancer")

OUTSIDER = ChatActor("u2", "umkm")


def make_conversation(
    conversation_id="c1",
    umkm_id="u1",
    freelancer_id="f1",
    project_id=None,
):
    return Conversation(
        id=conversation_id,
        umkm_id=umkm_id,
        freelancer_id=freelancer_id,
        project_id=project_id,
        last_message_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def make_message(
    message_id,
    sender_id="u1",
    conversation_id="c1",
    sent_at=NOW,
    read_at=None,
):
    return Message(
        id=message_id,
        conversation_id=conversation_id,
        sender_user_id=sender_id,
        message_text="Hello",
        message_type=MessageType.TEXT,
        sent_at=sent_at,
        created_at=sent_at,
        read_at=read_at,
    )


# ============================================================
# 2. FAKE REPOSITORY
# ============================================================

class FakeChatRepository:
    """
    Fake ConversationRepository + MessageRepository.

    Hanya digunakan dalam unit testing.
    """

    def __init__(self):

        self.roles = {
            "u1": "umkm",
            "u2": "umkm",
            "f1": "freelancer",
            "f2": "freelancer",
        }

        self.project_owners = {
            "p1": "u1",
            "p2": "u2",
        }

        self.conversations = {
            "c1": make_conversation(),
        }

        self.messages = []
        self.attachments = []

        self.create_calls = 0
        self.send_calls = 0
        self.read_calls = 0

        self.return_wrong_conversation = False
        self.return_wrong_message = False
        self.return_invalid_read_count = False

    # ========================================================
    # CONVERSATION METHODS
    # ========================================================

    def get_user_role(self, user_id):
        return self.roles.get(user_id)

    def get_project_owner_id(self, project_id):
        return self.project_owners.get(project_id)

    def find_by_participants(
        self,
        umkm_id,
        freelancer_id,
        project_id,
    ):
        for item in self.conversations.values():
            if (
                item.umkm_id == umkm_id
                and item.freelancer_id == freelancer_id
                and item.project_id == project_id
            ):
                return item

        return None

    def get_by_id(self, conversation_id):
        return self.conversations.get(
            conversation_id
        )

    def list_for_user(
        self,
        user_id,
        *,
        limit,
        offset,
    ):
        items = [
            item
            for item in self.conversations.values()
            if user_id in (
                item.umkm_id,
                item.freelancer_id,
            )
        ]

        items.sort(
            key=lambda item: (
                item.last_message_at or item.created_at,
                item.id,
            ),
            reverse=True,
        )

        return tuple(
            items[offset:offset + limit]
        )

    def create_or_get(self, conversation):

        self.create_calls += 1

        if self.return_wrong_conversation:
            return make_conversation(
                "wrong",
                "u2",
                "f2",
            )

        existing = self.find_by_participants(
            conversation.umkm_id,
            conversation.freelancer_id,
            conversation.project_id,
        )

        if existing is not None:
            return existing

        self.conversations[
            conversation.id
        ] = conversation

        return conversation

    # ========================================================
    # MESSAGE METHODS
    # ========================================================

    def list_for_conversation(
        self,
        conversation_id,
        *,
        limit,
        before=None,
    ):
        items = [
            item
            for item in self.messages
            if item.conversation_id == conversation_id
        ]

        items.sort(
            key=lambda item: (
                item.sent_at,
                item.id,
            ),
            reverse=True,
        )

        if before is not None:
            items = [
                item
                for item in items
                if (
                    item.sent_at,
                    item.id,
                ) < before
            ]

        return tuple(items[:limit])

    def list_attachments(
        self,
        message_ids,
    ):
        return tuple(
            attachment
            for attachment in self.attachments
            if attachment.message_id in message_ids
        )

    def create_with_attachments(
        self,
        message,
        attachments,
    ):
        self.send_calls += 1

        if self.return_wrong_message:
            return replace(
                message,
                sender_user_id="other",
            )

        self.messages.append(message)
        self.attachments.extend(attachments)

        conversation = self.conversations[
            message.conversation_id
        ]

        self.conversations[
            conversation.id
        ] = replace(
            conversation,
            last_message_at=message.sent_at,
            updated_at=message.sent_at,
        )

        return message

    def get_message_by_id(self, message_id):
        for message in self.messages:
            if message.id == message_id:
                return message

        return None

    def mark_received_messages_read(
        self,
        conversation_id,
        recipient_user_id,
        read_at,
    ):
        self.read_calls += 1

        if self.return_invalid_read_count:
            return -1

        conversation = self.get_by_id(
            conversation_id
        )

        allowed_senders = {
            conversation.umkm_id,
            conversation.freelancer_id,
        }

        updated = 0

        for index, message in enumerate(self.messages):

            if (
                message.conversation_id == conversation_id
                and message.sender_user_id
                in allowed_senders
                and message.sender_user_id
                != recipient_user_id
                and message.read_at is None
            ):
                self.messages[index] = replace(
                    message,
                    read_at=read_at,
                )

                updated += 1

        return updated


# ============================================================
# 3. FIXTURE
# ============================================================

@pytest.fixture
def repo():
    return FakeChatRepository()


# ============================================================
# 4. CREATE CONVERSATION TESTS
# ============================================================

def test_create_general_conversation(repo):
    repo.conversations.clear()

    result = CreateOrGetConversation(
        repo,
        clock=lambda: NOW,
    ).execute(
        CreateConversationInput(
            actor=UMKM,
            counterpart_user_id="f1",
        )
    )

    assert result.umkm_id == "u1"
    assert result.freelancer_id == "f1"
    assert result.project_id is None

    assert repo.create_calls == 1


def test_freelancer_can_initiate_chat(repo):
    repo.conversations.clear()

    result = CreateOrGetConversation(
        repo,
        clock=lambda: NOW,
    ).execute(
        CreateConversationInput(
            actor=FREELANCER,
            counterpart_user_id="u1",
        )
    )

    assert result.umkm_id == "u1"
    assert result.freelancer_id == "f1"


def test_existing_conversation_is_reused(repo):
    result = CreateOrGetConversation(
        repo
    ).execute(
        CreateConversationInput(
            actor=UMKM,
            counterpart_user_id="f1",
        )
    )

    assert result.id == "c1"
    assert repo.create_calls == 0


def test_create_project_conversation(repo):
    result = CreateOrGetConversation(
        repo,
        clock=lambda: NOW,
    ).execute(
        CreateConversationInput(
            actor=UMKM,
            counterpart_user_id="f1",
            project_id="p1",
        )
    )

    assert result.project_id == "p1"
    assert repo.create_calls == 1


def test_project_owner_mismatch_rejected(repo):
    with pytest.raises(NotFoundError):
        CreateOrGetConversation(
            repo
        ).execute(
            CreateConversationInput(
                actor=UMKM,
                counterpart_user_id="f1",
                project_id="p2",
            )
        )

    assert repo.create_calls == 0


def test_unknown_counterpart_rejected(repo):
    with pytest.raises(NotFoundError):
        CreateOrGetConversation(
            repo
        ).execute(
            CreateConversationInput(
                actor=UMKM,
                counterpart_user_id="unknown",
            )
        )


def test_same_user_rejected(repo):
    with pytest.raises(BadRequestError):
        CreateOrGetConversation(
            repo
        ).execute(
            CreateConversationInput(
                actor=UMKM,
                counterpart_user_id="u1",
            )
        )


def test_wrong_counterpart_role_rejected(repo):
    with pytest.raises(NotFoundError):
        CreateOrGetConversation(
            repo
        ).execute(
            CreateConversationInput(
                actor=UMKM,
                counterpart_user_id="u2",
            )
        )


def test_invalid_actor_rejected(repo):
    with pytest.raises(ForbiddenError):
        CreateOrGetConversation(
            repo
        ).execute(
            CreateConversationInput(
                actor=ChatActor(
                    "admin1",
                    "admin",
                ),
                counterpart_user_id="f1",
            )
        )


def test_wrong_repository_conversation_rejected(repo):
    repo.conversations.clear()
    repo.return_wrong_conversation = True

    with pytest.raises(ConflictError):
        CreateOrGetConversation(
            repo
        ).execute(
            CreateConversationInput(
                actor=UMKM,
                counterpart_user_id="f1",
            )
        )


# ============================================================
# 5. GET CONVERSATION TESTS
# ============================================================

def test_umkm_get_conversation(repo):
    result = GetConversation(repo).execute(
        GetConversationInput(
            "c1",
            UMKM,
        )
    )

    assert result.id == "c1"


def test_freelancer_get_conversation(repo):
    result = GetConversation(repo).execute(
        GetConversationInput(
            "c1",
            FREELANCER,
        )
    )

    assert result.id == "c1"


def test_outsider_cannot_get_conversation(repo):
    with pytest.raises(NotFoundError):
        GetConversation(repo).execute(
            GetConversationInput(
                "c1",
                OUTSIDER,
            )
        )


def test_missing_conversation(repo):
    with pytest.raises(NotFoundError):
        GetConversation(repo).execute(
            GetConversationInput(
                "missing",
                UMKM,
            )
        )


# ============================================================
# 6. LIST CONVERSATIONS TESTS
# ============================================================

def test_list_own_conversations(repo):
    result = ListUserConversations(
        repo
    ).execute(
        ListConversationsInput(
            actor=UMKM,
        )
    )

    assert len(result.items) == 1
    assert result.items[0].id == "c1"


def test_list_filters_other_users(repo):
    result = ListUserConversations(
        repo
    ).execute(
        ListConversationsInput(
            actor=OUTSIDER,
        )
    )

    assert result.items == ()


@pytest.mark.parametrize(
    "limit",
    [0, 101, True],
)
def test_invalid_conversation_limit(repo, limit):
    with pytest.raises(BadRequestError):
        ListUserConversations(
            repo
        ).execute(
            ListConversationsInput(
                actor=UMKM,
                limit=limit,
            )
        )


@pytest.mark.parametrize(
    "offset",
    [-1, True],
)
def test_invalid_conversation_offset(repo, offset):
    with pytest.raises(BadRequestError):
        ListUserConversations(
            repo
        ).execute(
            ListConversationsInput(
                actor=UMKM,
                offset=offset,
            )
        )


# ============================================================
# 7. SEND TEXT MESSAGE TESTS
# ============================================================

def test_send_text_message(repo):
    result = SendTextMessage(
        repo,
        repo,
        clock=lambda: NOW,
    ).execute(
        SendTextMessageInput(
            conversation_id="c1",
            actor=UMKM,
            message_text="  Halo Freelancer!  ",
        )
    )

    assert result.sender_user_id == "u1"
    assert result.message_text == "Halo Freelancer!"
    assert result.message_type == MessageType.TEXT

    assert repo.send_calls == 1
    assert repo.conversations["c1"].last_message_at == NOW


def test_freelancer_can_reply(repo):
    result = SendTextMessage(
        repo,
        repo,
        clock=lambda: NOW,
    ).execute(
        SendTextMessageInput(
            "c1",
            FREELANCER,
            "Siap, Kak!",
        )
    )

    assert result.sender_user_id == "f1"


@pytest.mark.parametrize(
    "text",
    [None, "", "   "],
)
def test_empty_message_rejected(repo, text):
    with pytest.raises(BadRequestError):
        SendTextMessage(
            repo,
            repo,
        ).execute(
            SendTextMessageInput(
                "c1",
                UMKM,
                text,
            )
        )

    assert repo.send_calls == 0


def test_outsider_cannot_send_message(repo):
    with pytest.raises(NotFoundError):
        SendTextMessage(
            repo,
            repo,
        ).execute(
            SendTextMessageInput(
                "c1",
                OUTSIDER,
                "Pesan tidak sah",
            )
        )

    assert repo.send_calls == 0


def test_wrong_saved_message_rejected(repo):
    repo.return_wrong_message = True

    with pytest.raises(ConflictError):
        SendTextMessage(
            repo,
            repo,
        ).execute(
            SendTextMessageInput(
                "c1",
                UMKM,
                "Hello",
            )
        )


# ============================================================
# 8. MESSAGE HISTORY TESTS
# ============================================================

def test_empty_message_history(repo):
    result = ListConversationMessages(
        repo,
        repo,
    ).execute(
        ListMessagesInput(
            "c1",
            UMKM,
        )
    )

    assert result.items == ()
    assert result.has_more is False
    assert result.next_before is None


def test_message_history_order(repo):
    repo.messages = [
        make_message(
            "m1",
            sent_at=NOW,
        ),
        make_message(
            "m2",
            sender_id="f1",
            sent_at=NOW + timedelta(minutes=1),
        ),
    ]

    result = ListConversationMessages(
        repo,
        repo,
    ).execute(
        ListMessagesInput(
            "c1",
            UMKM,
        )
    )

    assert [
        item.message.id
        for item in result.items
    ] == ["m2", "m1"]


def test_keyset_pagination(repo):
    repo.messages = [
        make_message(
            f"m{i}",
            sent_at=NOW + timedelta(minutes=i),
        )
        for i in range(3)
    ]

    use_case = ListConversationMessages(
        repo,
        repo,
    )

    first = use_case.execute(
        ListMessagesInput(
            "c1",
            UMKM,
            limit=2,
        )
    )

    assert len(first.items) == 2
    assert first.has_more is True
    assert first.next_before is not None

    second = use_case.execute(
        ListMessagesInput(
            "c1",
            UMKM,
            limit=2,
            before=first.next_before,
        )
    )

    assert len(second.items) == 1
    assert second.has_more is False

    assert [
        item.message.id
        for item in first.items
    ] == ["m2", "m1"]

    assert second.items[0].message.id == "m0"


def test_outsider_cannot_read_messages(repo):
    with pytest.raises(NotFoundError):
        ListConversationMessages(
            repo,
            repo,
        ).execute(
            ListMessagesInput(
                "c1",
                OUTSIDER,
            )
        )


def test_invalid_message_page_limit(repo):
    with pytest.raises(BadRequestError):
        ListConversationMessages(
            repo,
            repo,
        ).execute(
            ListMessagesInput(
                "c1",
                UMKM,
                limit=0,
            )
        )


def test_invalid_message_cursor(repo):
    with pytest.raises(BadRequestError):
        ListConversationMessages(
            repo,
            repo,
        ).execute(
            ListMessagesInput(
                "c1",
                UMKM,
                before=("invalid", "m1"),
            )
        )


def test_message_history_with_attachment(repo):
    repo.messages = [
        make_message("m1"),
    ]

    repo.attachments = [
        MessageAttachment(
            id="a1",
            message_id="m1",
            original_file_name="brief.pdf",
            storage_key="chat/m1/brief.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            uploaded_at=NOW,
        ),
    ]

    result = ListConversationMessages(
        repo,
        repo,
    ).execute(
        ListMessagesInput(
            "c1",
            UMKM,
        )
    )

    assert len(result.items) == 1
    assert len(result.items[0].attachments) == 1


def test_forged_message_sender_rejected(repo):
    repo.messages = [
        make_message(
            "m1",
            sender_id="outsider",
        ),
    ]

    with pytest.raises(ConflictError):
        ListConversationMessages(
            repo,
            repo,
        ).execute(
            ListMessagesInput(
                "c1",
                UMKM,
            )
        )


# ============================================================
# 9. MARK MESSAGES AS READ
# ============================================================

def test_mark_received_messages_read(repo):
    repo.messages = [
        make_message(
            "m1",
            sender_id="u1",
        ),
        make_message(
            "m2",
            sender_id="f1",
        ),
    ]

    use_case = MarkConversationRead(
        repo,
        repo,
        clock=lambda: NOW,
    )

    result = use_case.execute(
        MarkConversationReadInput(
            "c1",
            UMKM,
        )
    )

    assert result.marked_count == 1

    # Pesan sendiri tidak ikut ditandai.
    assert repo.messages[0].read_at is None

    # Pesan dari pihak lain sudah dibaca.
    assert repo.messages[1].read_at == NOW


def test_mark_read_is_idempotent(repo):
    repo.messages = [
        make_message(
            "m1",
            sender_id="f1",
        ),
    ]

    use_case = MarkConversationRead(
        repo,
        repo,
        clock=lambda: NOW,
    )

    first = use_case.execute(
        MarkConversationReadInput(
            "c1",
            UMKM,
        )
    )

    second = use_case.execute(
        MarkConversationReadInput(
            "c1",
            UMKM,
        )
    )

    assert first.marked_count == 1
    assert second.marked_count == 0


def test_outsider_cannot_mark_read(repo):
    with pytest.raises(NotFoundError):
        MarkConversationRead(
            repo,
            repo,
        ).execute(
            MarkConversationReadInput(
                "c1",
                OUTSIDER,
            )
        )

    assert repo.read_calls == 0


def test_invalid_read_count_rejected(repo):
    repo.return_invalid_read_count = True

    with pytest.raises(ConflictError):
        MarkConversationRead(
            repo,
            repo,
        ).execute(
            MarkConversationReadInput(
                "c1",
                UMKM,
            )
        )