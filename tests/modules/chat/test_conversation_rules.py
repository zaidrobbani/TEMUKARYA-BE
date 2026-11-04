from datetime import datetime, timezone

import pytest

from app.modules.chat.domain.entities import (
    ChatActor,
    Conversation,
)

from app.modules.chat.domain.conversation_rules import (
    validate_chat_id,
    validate_conversation_participants,
    conversation_identity_key,
    require_chat_actor,
    require_conversation_access,
    require_conversation_initiator,
    require_project_owner,
)


NOW = datetime(
    2026, 11, 4,
    tzinfo=timezone.utc,
)


# ============================================================
# HELPER
# ============================================================

def conv(project=None):
    return Conversation(
        "c1", "u1", "f1",
        project, None, NOW, NOW,
    )


# ============================================================
# 1. VALIDATE ID
# ============================================================

def test_valid_chat_id():
    assert validate_chat_id(
        "  user1 "
    ) == "user1"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        "x" * 37,
        "a/b",
        "a\\b",
        "a\x00b",
        None,
        123,
    ],
)
def test_invalid_chat_id(bad):
    with pytest.raises(ValueError):
        validate_chat_id(bad)


# ============================================================
# 2. VALIDATE PARTICIPANTS
# ============================================================

def test_validate_general_participants():
    assert validate_conversation_participants(
        "u1", "f1"
    ) == (
        "u1", "f1", None
    )


def test_validate_project_participants():
    assert validate_conversation_participants(
        "u1", "f1", "p1"
    ) == (
        "u1", "f1", "p1"
    )


def test_reject_same_user():
    with pytest.raises(ValueError):
        validate_conversation_participants(
            "same", "same"
        )


def test_reject_blank_project():
    with pytest.raises(ValueError):
        validate_conversation_participants(
            "u1", "f1", "  "
        )


def test_identity_key_distinguishes_general_from_project():
    assert conversation_identity_key(
        "u1", "f1"
    ) != conversation_identity_key(
        "u1", "f1", "p1"
    )


# ============================================================
# 3. VALIDATE CHAT ACTOR
# ============================================================

@pytest.mark.parametrize(
    "actor",
    [
        ChatActor("u1", "umkm"),
        ChatActor("f1", "freelancer"),
    ],
)
def test_valid_actor(actor):
    require_chat_actor(actor)


@pytest.mark.parametrize(
    "actor",
    [
        None,
        ChatActor("", "umkm"),
        ChatActor("u1", "admin"),
    ],
)
def test_invalid_actor(actor):
    with pytest.raises(PermissionError):
        require_chat_actor(actor)


# ============================================================
# 4. CONVERSATION ACCESS
# ============================================================

@pytest.mark.parametrize(
    "actor",
    [
        ChatActor("u1", "umkm"),
        ChatActor("f1", "freelancer"),
    ],
)
def test_participant_access(actor):
    require_conversation_access(
        conv(), actor
    )


@pytest.mark.parametrize(
    "actor",
    [
        ChatActor("outsider", "umkm"),
        ChatActor("u1", "freelancer"),
        ChatActor("f1", "umkm"),
    ],
)
def test_reject_nonparticipant_or_wrong_role(actor):
    with pytest.raises(PermissionError):
        require_conversation_access(
            conv(), actor
        )


# ============================================================
# 5. CONVERSATION INITIATOR
# ============================================================

@pytest.mark.parametrize(
    "actor",
    [
        ChatActor("u1", "umkm"),
        ChatActor("f1", "freelancer"),
    ],
)
def test_initiator_is_participant(actor):
    require_conversation_initiator(
        actor, "u1", "f1"
    )


def test_reject_fake_initiator():
    with pytest.raises(PermissionError):
        require_conversation_initiator(
            ChatActor("other", "umkm"),
            "u1",
            "f1",
        )


# ============================================================
# 6. PROJECT OWNERSHIP
# ============================================================

def test_general_chat_needs_no_project_owner():
    require_project_owner(
        conv(), None
    )


def test_project_owner_matches():
    require_project_owner(
        conv("p1"), "u1"
    )


@pytest.mark.parametrize(
    "owner",
    [
        None,
        "different",
    ],
)
def test_project_owner_mismatch_rejected(owner):
    with pytest.raises(PermissionError):
        require_project_owner(
            conv("p1"), owner
        )