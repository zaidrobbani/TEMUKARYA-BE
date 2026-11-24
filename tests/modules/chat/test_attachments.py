import io
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.core.error_handlers import register_error_handlers
from app.modules.chat.application.dto import SendAttachmentMessageInput
from app.modules.chat.application.use_cases import SendAttachmentMessage
from app.modules.chat.domain.attachment_storage import (
    CHAT_IMAGE_MAX_BYTES,
    CHAT_IMAGE_MAX_DIMENSION,
    CHAT_THUMBNAIL_DIMENSION,
    CHAT_THUMBNAIL_MAX_BYTES,
)
from app.modules.chat.infrastructure.attachment_storage import LocalChatAttachmentStorage
from app.modules.chat.presentation.dependencies import (
    get_authenticated_chat_actor,
    get_chat_attachment_storage,
    get_chat_database_context,
    get_new_message_hook,
)
from app.modules.chat.presentation.realtime import (
    ChatHub,
    get_chat_context_factory,
    get_chat_hub,
    get_socket_authenticator,
    get_socket_message_notifier,
)
from app.modules.chat.presentation.router import router
from tests.modules.chat.test_router import (
    FREELANCER,
    OUTSIDER,
    UMKM,
    FakeChatContext,
    FakeConversationRepository,
    FakeMessageRepository,
    FakeSession,
)

UPLOAD_URL = "/conversations/c1/attachments"


def photo(size=(3000, 2000), fmt="JPEG") -> bytes:
    picture = Image.effect_noise(size, 70).convert("RGB")
    buffer = io.BytesIO()
    picture.save(buffer, format=fmt, quality=85)
    return buffer.getvalue()


def smooth_photo(size=(3000, 2000)) -> bytes:
    # Mirip foto asli (gradasi halus), bukan noise acak.
    r = Image.linear_gradient("L").resize(size)
    g = Image.linear_gradient("L").rotate(90).resize(size)
    picture = Image.merge("RGB", (r, g, Image.new("L", size, 120)))
    buffer = io.BytesIO()
    picture.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def office(marker: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(f"{marker}document.xml", "<doc/>")
    return buffer.getvalue()


@pytest.fixture
def chat(tmp_path):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    conversations = FakeConversationRepository()
    context = FakeChatContext(FakeSession(), conversations, FakeMessageRepository(conversations))
    storage = LocalChatAttachmentStorage(tmp_path / "chat")
    hub = ChatHub()
    notified = []
    actor = {"value": UMKM}

    from contextlib import contextmanager

    @contextmanager
    def open_context():
        yield context

    app.dependency_overrides.update({
        get_chat_database_context: lambda: context,
        get_authenticated_chat_actor: lambda: actor["value"],
        get_new_message_hook: lambda: lambda *args: notified.append(args),
        get_chat_attachment_storage: lambda: storage,
        get_chat_hub: lambda: hub,
        get_chat_context_factory: lambda: open_context,
        get_socket_authenticator: lambda: lambda token: {"umkm": UMKM, "freelancer": FREELANCER}[token],
        get_socket_message_notifier: lambda: lambda *args: None,
    })
    with TestClient(app) as client:
        yield client, actor, context, storage, notified


def upload(client, data, name, mime, caption=None):
    form = {"caption": caption} if caption is not None else None
    return client.post(UPLOAD_URL, files={"file": (name, data, mime)}, data=form)


def stored(storage):
    return sorted(p.name for p in storage.root.iterdir() if not p.name.startswith("."))


class TestPhoto:
    def test_large_photo_is_compressed_with_thumbnail(self, chat):
        client, _, context, storage, notified = chat

        response = upload(client, smooth_photo(), "IMG_2026.jpg", "image/jpeg", caption="  Draf logo  ")

        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["message"]["message_type"] == "IMAGE"
        assert data["message"]["message_text"] == "Draf logo"
        [attachment] = data["attachments"]
        assert attachment["mime_type"] == "image/webp"
        assert attachment["original_file_name"] == "IMG_2026.webp"
        assert attachment["file_size_bytes"] <= CHAT_IMAGE_MAX_BYTES
        assert attachment["download_path"].endswith(f"/attachments/{attachment['id']}/file")
        assert attachment["thumbnail_path"].endswith("?thumbnail=true")
        full_name, thumb_name = stored(storage)[1], stored(storage)[0]
        with Image.open(storage.root / full_name) as full:
            assert max(full.size) == CHAT_IMAGE_MAX_DIMENSION
        with Image.open(storage.root / thumb_name) as thumb:
            assert max(thumb.size) <= CHAT_THUMBNAIL_DIMENSION
        assert (storage.root / thumb_name).stat().st_size <= CHAT_THUMBNAIL_MAX_BYTES
        assert context.session.commits == 1
        assert notified[0][2] == "Draf logo"

    def test_hard_to_compress_photo_still_within_limit(self, chat):
        client, *_ = chat
        attachment = upload(client, photo((2400, 1600)), "noise.jpg", "image/jpeg").json()["data"]["attachments"][0]
        assert attachment["file_size_bytes"] <= CHAT_IMAGE_MAX_BYTES

    def test_photo_without_caption_notifies_with_label(self, chat):
        client, _, _, _, notified = chat
        assert upload(client, photo((800, 600), "PNG"), "a.png", "image/png").status_code == 201
        assert notified[0][2] == "📷 Foto"

    def test_full_and_thumbnail_can_be_downloaded_by_participant(self, chat):
        client, actor, *_ = chat
        attachment = upload(client, photo((900, 900)), "a.jpg", "image/jpeg").json()["data"]["attachments"][0]
        actor["value"] = FREELANCER
        url = f"/conversations/c1/attachments/{attachment['id']}/file"

        full = client.get(url)
        thumb = client.get(url, params={"thumbnail": "true"})

        assert full.status_code == thumb.status_code == 200
        assert full.headers["content-type"] == thumb.headers["content-type"] == "image/webp"
        assert len(thumb.content) < len(full.content)


class TestDocument:
    def test_pdf_is_stored_as_is(self, chat):
        client, actor, *_ = chat
        pdf = b"%PDF-1.7\n" + b"isi" * 100
        data = upload(client, pdf, "Brief Desain.pdf", "application/pdf").json()["data"]
        attachment = data["attachments"][0]
        assert data["message"]["message_type"] == "FILE"
        assert attachment["mime_type"] == "application/pdf"
        assert attachment["original_file_name"] == "Brief Desain.pdf"
        assert attachment["thumbnail_path"] is None
        actor["value"] = FREELANCER
        assert client.get(attachment["download_path"].removeprefix("/api/v1")).content == pdf

    @pytest.mark.parametrize(("name", "marker", "mime"), [
        ("laporan.docx", "word/", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("anggaran.xlsx", "xl/", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("pitch.pptx", "ppt/", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ("aset.zip", "apa/", "application/zip"),
    ])
    def test_office_and_zip(self, chat, name, marker, mime):
        client, *_ = chat
        response = upload(client, office(marker), name, "application/octet-stream")
        assert response.status_code == 201, response.text
        assert response.json()["data"]["attachments"][0]["mime_type"] == mime

    def test_text_and_csv(self, chat):
        client, *_ = chat
        assert upload(client, "catatan revisi".encode(), "c.txt", "text/plain").json()["data"]["attachments"][0]["mime_type"] == "text/plain"
        assert upload(client, b"a,b\n1,2", "d.csv", "text/csv").json()["data"]["attachments"][0]["mime_type"] == "text/csv"

    @pytest.mark.parametrize(("data", "name", "status"), [
        (b"MZ\x90\x00program", "setup.pdf", 415),
        (b"\x00\x01\x02 biner acak", "data.bin", 415),
        (b"\xff\xfe\x00 bukan utf8", "c.txt", 415),
        (office("word/"), "salah.xlsx", 400),
        (b"", "kosong.pdf", 400),
        (b"%PDF-" + b"0" * (10 * 1024 * 1024), "besar.pdf", 413),
    ])
    def test_rejected_files(self, chat, data, name, status):
        client, _, context, storage, _ = chat
        response = upload(client, data, name, "application/octet-stream")
        assert response.status_code == status, response.text
        assert stored(storage) == []
        assert context.messages.messages == []


class TestAccessAndRealtime:
    def test_outsider_cannot_upload_or_download(self, chat):
        client, actor, *_ = chat
        attachment = upload(client, b"%PDF-1.4 x", "a.pdf", "application/pdf").json()["data"]["attachments"][0]
        actor["value"] = OUTSIDER
        assert upload(client, b"%PDF-1.4 x", "b.pdf", "application/pdf").status_code in (403, 404)
        assert client.get(f"/conversations/c1/attachments/{attachment['id']}/file").status_code in (403, 404)

    def test_unknown_attachment_returns_404(self, chat):
        client, *_ = chat
        assert client.get("/conversations/c1/attachments/tidak-ada/file").status_code == 404

    def test_upload_is_pushed_to_websocket_with_attachment(self, chat):
        client, *_ = chat
        with client.websocket_connect("/conversations/c1/ws?token=freelancer") as ws:
            ws.receive_json()
            upload(client, photo((600, 400)), "a.jpg", "image/jpeg")
            event = ws.receive_json()
        assert event["type"] == "message"
        assert event["message"]["message_type"] == "IMAGE"
        assert event["attachments"][0]["thumbnail_path"].endswith("?thumbnail=true")

    def test_history_includes_attachment_paths(self, chat):
        client, *_ = chat
        upload(client, b"%PDF-1.4 x", "a.pdf", "application/pdf")
        item = client.get("/conversations/c1/messages").json()["data"]["items"][0]
        assert item["attachments"][0]["download_path"].startswith("/api/v1/conversations/c1/attachments/")


def test_failed_save_removes_stored_files(tmp_path):
    conversations = FakeConversationRepository()
    messages = FakeMessageRepository(conversations)
    storage = LocalChatAttachmentStorage(tmp_path)

    def broken(**_):
        raise RuntimeError("db down")

    messages.create_with_attachments = broken
    with pytest.raises(RuntimeError):
        SendAttachmentMessage(conversations, messages, storage).execute(
            SendAttachmentMessageInput("c1", UMKM, "a.jpg", io.BytesIO(photo((500, 500))), is_image=True)
        )
    assert list(tmp_path.iterdir()) == []
