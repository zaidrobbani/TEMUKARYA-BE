from app.modules.chat.domain.entities import (
    ChatActor,
    Conversation,
)
from app.modules.users.domain.entities import UserRole


# ============================================================
# 1. VALID CHAT ROLES
# ============================================================

VALID_CHAT_ROLES = frozenset({
    UserRole.UMKM,
    UserRole.FREELANCER,
})


# ============================================================
# 2. VALIDATE CHAT ID
# ============================================================

def validate_chat_id(
    value: str,
    field: str = "ID",
) -> str:
    """
    Validasi dasar ID di Domain Layer.

    Pemeriksaan format UUID yang ketat
    dilakukan pada boundary API.
    """

    if not isinstance(value, str):
        raise ValueError(
            f"{field} harus berupa string"
        )

    normalized = value.strip()

    if (
        not normalized
        or len(normalized) > 36
        or any(
            character in normalized
            for character in (
                "/",
                "\\",
                "\x00",
            )
        )
    ):
        raise ValueError(
            f"{field} tidak valid"
        )

    return normalized


# ============================================================
# 3. VALIDATE CONVERSATION PARTICIPANTS
# ============================================================

def validate_conversation_participants(
    umkm_id: str,
    freelancer_id: str,
    project_id: str | None = None,
) -> tuple[str, str, str | None]:
    """
    Memastikan peserta percakapan valid.

    UMKM dan Freelancer tidak boleh
    merupakan pengguna yang sama.
    """

    umkm = validate_chat_id(
        umkm_id,
        "UMKM ID",
    )

    freelancer = validate_chat_id(
        freelancer_id,
        "Freelancer ID",
    )

    project = (
        validate_chat_id(
            project_id,
            "Project ID",
        )
        if project_id is not None
        else None
    )

    if umkm == freelancer:
        raise ValueError(
            "UMKM dan Freelancer harus berbeda pengguna"
        )

    return umkm, freelancer, project


# ============================================================
# 4. CONVERSATION IDENTITY KEY
# ============================================================

def conversation_identity_key(
    umkm_id: str,
    freelancer_id: str,
    project_id: str | None = None,
) -> tuple[str, str, str | None]:
    """
    Identitas unik sebuah percakapan.

    Digunakan untuk membedakan:
    - Chat umum
    - Chat untuk project tertentu

    Database tetap wajib menggunakan
    unique constraint untuk mencegah
    duplicate saat request bersamaan.
    """

    return validate_conversation_participants(
        umkm_id,
        freelancer_id,
        project_id,
    )


# ============================================================
# 5. REQUIRE VALID CHAT ACTOR
# ============================================================

def require_chat_actor(
    actor: ChatActor,
) -> None:
    """
    Pastikan pengguna memiliki identitas
    dan role yang diizinkan.
    """

    if not isinstance(actor, ChatActor):
        raise PermissionError(
            "Identitas pengguna tidak valid"
        )

    try:
        validate_chat_id(
            actor.user_id,
            "User ID",
        )
    except ValueError as exc:
        raise PermissionError(
            "Identitas pengguna tidak valid"
        ) from exc

    if actor.role not in VALID_CHAT_ROLES:
        raise PermissionError(
            "Role tidak diizinkan untuk chat"
        )


# ============================================================
# 6. REQUIRE CONVERSATION ACCESS
# ============================================================

def require_conversation_access(
    conversation: Conversation,
    actor: ChatActor,
) -> None:
    """
    Hanya dua peserta resmi yang boleh
    mengakses percakapan.
    """

    require_chat_actor(actor)

    umkm, freelancer, _ = (
        validate_conversation_participants(
            conversation.umkm_id,
            conversation.freelancer_id,
            conversation.project_id,
        )
    )

    owner_allowed = (
        actor.role == UserRole.UMKM
        and actor.user_id == umkm
    )

    freelancer_allowed = (
        actor.role == UserRole.FREELANCER
        and actor.user_id == freelancer
    )

    if not (
        owner_allowed
        or freelancer_allowed
    ):
        raise PermissionError(
            "Pengguna bukan peserta percakapan"
        )


# ============================================================
# 7. REQUIRE CONVERSATION INITIATOR
# ============================================================

def require_conversation_initiator(
    actor: ChatActor,
    umkm_id: str,
    freelancer_id: str,
    project_id: str | None = None,
) -> None:
    """
    Memvalidasi pihak yang ingin membuat chat.

    UMKM hanya bisa membuat chat sebagai UMKM.
    Freelancer hanya bisa membuat chat
    sebagai Freelancer.
    """

    umkm, freelancer, _ = (
        validate_conversation_participants(
            umkm_id,
            freelancer_id,
            project_id,
        )
    )

    require_chat_actor(actor)

    is_umkm = (
        actor.role == UserRole.UMKM
        and actor.user_id == umkm
    )

    is_freelancer = (
        actor.role == UserRole.FREELANCER
        and actor.user_id == freelancer
    )

    if not (is_umkm or is_freelancer):
        raise PermissionError(
            "Pengguna tidak dapat memulai percakapan ini"
        )


# ============================================================
# 8. REQUIRE PROJECT OWNER
# ============================================================

def require_project_owner(
    conversation: Conversation,
    project_umkm_id: str | None,
) -> None:
    """
    Jika chat terhubung ke suatu project,
    UMKM peserta chat harus pemilik project.

    project_umkm_id harus diperoleh dari
    repository Projects yang tepercaya.
    """

    if conversation.project_id is None:
        return

    if (
        project_umkm_id is None
        or validate_chat_id(
            project_umkm_id,
            "Project owner ID",
        ) != conversation.umkm_id
    ):
        raise PermissionError(
            "Percakapan tidak sesuai pemilik project"
        )