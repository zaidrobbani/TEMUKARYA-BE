import io
import os

import pytest
from PIL import Image

from app.main import app
from app.modules.users.domain.avatar import AVATAR_MAX_DIMENSION, AVATAR_MAX_STORED_BYTES
from app.modules.users.infrastructure.avatar_storage import LocalAvatarStorage
from app.modules.users.presentation.dependencies import get_avatar_storage
from tests.api.test_auth_api import (  # noqa: F401 (fixture dipakai pytest)
    action_tokens,
    assert_error,
    auth,
    client,
    emails,
    google,
    token_of,
    users,
)


@pytest.fixture
def storage(tmp_path, client):
    store = LocalAvatarStorage(tmp_path / "avatars")
    app.dependency_overrides[get_avatar_storage] = lambda: store
    return store


def image_bytes(fmt="PNG", size=(1600, 1200), noise=True) -> bytes:
    picture = Image.effect_noise(size, 80).convert("RGB") if noise else Image.new("RGB", size, (200, 120, 40))
    buffer = io.BytesIO()
    picture.save(buffer, format=fmt)
    return buffer.getvalue()


def upload(client, token, data: bytes, name="foto.png", mime="image/png"):
    return client.put("/api/v1/users/me/photo", headers=auth(token), files={"file": (name, data, mime)})


def stored_files(storage):
    return sorted(p for p in os.listdir(storage.root) if p.endswith(".webp"))


class TestUploadPhoto:
    def test_large_photo_is_compressed_to_small_webp(self, client, storage):
        token = token_of(client)

        data = image_bytes("JPEG", (1600, 1200))
        assert len(data) <= 2 * 1024 * 1024

        response = upload(client, token, data, "foto.jpg", "image/jpeg")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["message"] == "Foto profil berhasil diperbarui"
        user_id = body["data"]["id"]
        assert body["data"]["profile_image_url"].startswith(f"/api/v1/users/{user_id}/photo?v=")
        [stored] = stored_files(storage)
        size = os.path.getsize(storage.root / stored)
        assert size <= AVATAR_MAX_STORED_BYTES
        with Image.open(storage.root / stored) as saved:
            assert saved.format == "WEBP"
            assert max(saved.size) <= AVATAR_MAX_DIMENSION
            assert saved.size == (512, 384)

    def test_photo_can_be_read_by_other_logged_in_user(self, client, storage):
        owner = token_of(client)
        user_id = upload(client, owner, image_bytes("JPEG")).json()["data"]["id"]
        other = token_of(client, email="andi@example.com")

        response = client.get(f"/api/v1/users/{user_id}/photo", headers=auth(other))

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/webp"
        assert response.content[:4] == b"RIFF" and response.content[8:12] == b"WEBP"

    def test_replacing_photo_deletes_old_file(self, client, storage):
        token = token_of(client)
        first = upload(client, token, image_bytes(noise=False)).json()["data"]["profile_image_url"]

        second = upload(client, token, image_bytes("JPEG")).json()["data"]["profile_image_url"]

        assert first != second
        assert len(stored_files(storage)) == 1

    def test_too_large_upload_returns_413(self, client, storage):
        token = token_of(client)

        response = upload(client, token, b"\x89PNG\r\n\x1a\n" + b"0" * (2 * 1024 * 1024))

        assert_error(response, 413, "Ukuran foto maksimal 2 MB")
        assert stored_files(storage) == []

    def test_non_image_returns_415(self, client, storage):
        token = token_of(client)

        assert_error(upload(client, token, b"%PDF-1.7 bukan foto", "cv.pdf", "application/pdf"), 415)

    def test_corrupt_image_returns_400(self, client, storage):
        token = token_of(client)

        response = upload(client, token, b"\x89PNG\r\n\x1a\n" + b"rusak" * 50)

        assert_error(response, 400, "Foto rusak atau tidak dapat dibaca")

    def test_empty_file_returns_400(self, client, storage):
        token = token_of(client)

        assert_error(upload(client, token, b""), 400, "File foto kosong")

    def test_requires_login(self, client, storage):
        response = client.put("/api/v1/users/me/photo", files={"file": ("a.png", image_bytes(), "image/png")})

        assert_error(response, 401)


class TestReadAndRemovePhoto:
    def test_user_without_photo_returns_404(self, client, storage):
        token = token_of(client)
        user_id = client.get("/api/v1/auth/me", headers=auth(token)).json()["data"]["id"]

        assert_error(client.get(f"/api/v1/users/{user_id}/photo", headers=auth(token)), 404, "Foto profil tidak ditemukan")

    def test_unknown_user_returns_404(self, client, storage):
        token = token_of(client)

        assert_error(client.get("/api/v1/users/tidak-ada/photo", headers=auth(token)), 404)

    def test_delete_photo_clears_url_and_file(self, client, storage):
        token = token_of(client)
        upload(client, token, image_bytes())

        response = client.delete("/api/v1/users/me/photo", headers=auth(token))

        assert response.status_code == 200
        assert response.json()["data"]["profile_image_url"] is None
        assert stored_files(storage) == []
