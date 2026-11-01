import asyncio
import io
import os
import time
from uuid import uuid4

import pytest
from PIL import Image
from starlette.requests import Request

from app.modules.profiles.domain.media import InvalidImage, MAX_IMAGE_BYTES, OversizedImage, StorageFailure, UnsupportedImage
from app.modules.profiles.infrastructure.media_cleanup import cleanup_orphans
from app.modules.profiles.infrastructure.media_storage import LocalImageStorage
from app.modules.profiles.presentation.media_upload import receive_image


def image_bytes(format="PNG", size=(20, 10), **options):
    stream = io.BytesIO()
    with Image.new("RGB", size, "red") as image:
        image.save(stream, format=format, **options)
    return stream.getvalue()


@pytest.mark.parametrize("format,mime", [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")])
def test_decode_reencode_stores_real_size_and_removes_metadata(tmp_path, format, mime):
    storage = LocalImageStorage(tmp_path)
    exif = Image.Exif()
    exif[270] = "Sensitive location metadata"
    exif[274] = 6
    result = storage.save_image(io.BytesIO(image_bytes(format, exif=exif)))
    assert result.mime_type == mime
    assert result.size == (tmp_path / result.key).stat().st_size
    with storage.open(result.key) as stream, Image.open(stream) as decoded:
        assert decoded.size == (10, 20)
        assert not decoded.getexif()
        assert "xmp" not in decoded.info and "icc_profile" not in decoded.info
    assert [p.name for p in tmp_path.iterdir()] == [result.key]
    storage.delete(result.key)
    storage.delete(result.key)  # Missing file deletion is idempotent.
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("data,error", [
    (b"", InvalidImage), (b"<svg></svg>", UnsupportedImage), (b"%PDF-1.4", UnsupportedImage),
    (b"video", UnsupportedImage), (b"\x89PNG\r\n\x1a\ninvalid", InvalidImage),
    (b"\xff\xd8broken", InvalidImage),
])
def test_invalid_images_leave_no_files(tmp_path, data, error):
    with pytest.raises(error):
        LocalImageStorage(tmp_path).save_image(io.BytesIO(data))
    assert not list(tmp_path.iterdir())


def test_oversize_source_stops_reading_and_cleans_temp(tmp_path):
    class Source:
        count = 0
        def read(self, size):
            assert size == 64 * 1024
            self.count += size
            assert self.count <= MAX_IMAGE_BYTES + size
            return b"x" * size
    source = Source()
    with pytest.raises(OversizedImage):
        LocalImageStorage(tmp_path).save_image(source)
    assert source.count == MAX_IMAGE_BYTES + 64 * 1024
    assert not list(tmp_path.iterdir())


def test_dimensions_corruption_animation_and_bomb_are_rejected(tmp_path, monkeypatch):
    storage = LocalImageStorage(tmp_path)
    with pytest.raises(InvalidImage):
        storage.save_image(io.BytesIO(image_bytes(size=(4097, 1))))
    good = image_bytes()
    with pytest.raises(InvalidImage):
        storage.save_image(io.BytesIO(good[:-15]))
    animation = io.BytesIO()
    first, second = Image.new("RGB", (4, 4), "red"), Image.new("RGB", (4, 4), "blue")
    first.save(animation, format="PNG", save_all=True, append_images=[second])
    with pytest.raises(InvalidImage):
        storage.save_image(io.BytesIO(animation.getvalue()))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)
    with pytest.raises(InvalidImage):
        storage.save_image(io.BytesIO(good))
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("key", ["../secret", "/etc/passwd", "folder/file.png", "..\\secret", "test.jpg"])
def test_storage_traversal_is_rejected(tmp_path, key):
    storage = LocalImageStorage(tmp_path)
    with pytest.raises(StorageFailure):
        storage.open(key)
    with pytest.raises(StorageFailure):
        storage.delete(key)


def test_storage_symlink_is_rejected(tmp_path):
    storage = LocalImageStorage(tmp_path / "root")
    secret = tmp_path / "secret"
    secret.write_bytes(b"private")
    key = uuid4().hex + ".png"
    (storage.root / key).symlink_to(secret)
    with pytest.raises(StorageFailure):
        storage.open(key)
    with pytest.raises(StorageFailure):
        storage.delete(key)
    assert secret.read_bytes() == b"private"


def test_atomic_move_failure_cleans_temporaries(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError("disk failed")
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(StorageFailure):
        LocalImageStorage(tmp_path).save_image(io.BytesIO(image_bytes()))
    assert not list(tmp_path.iterdir())


def test_normalized_size_limit(tmp_path, monkeypatch):
    original = Image.Image.save
    def inflated(image, destination, **kwargs):
        original(image, destination, **kwargs)
        destination.write(b"x" * MAX_IMAGE_BYTES)
    good = image_bytes()
    monkeypatch.setattr(Image.Image, "save", inflated)
    with pytest.raises(OversizedImage):
        LocalImageStorage(tmp_path).save_image(io.BytesIO(good))
    assert not list(tmp_path.iterdir())


def test_orphan_cleanup_is_aged_dry_run_and_preserves_referenced_files(tmp_path):
    storage = LocalImageStorage(tmp_path)
    old, referenced, young = [uuid4().hex + ".png" for _ in range(3)]
    for name in [old, referenced, young, ".upload-old", "unrelated.txt"]:
        path = tmp_path / name
        path.write_bytes(b"data")
        if name != young:
            os.utime(path, (time.time() - 90000,) * 2)
    assert cleanup_orphans(storage, {referenced}) == sorted([old, ".upload-old"])
    assert (tmp_path / old).exists()
    cleanup_orphans(storage, {referenced}, apply=True)
    assert {p.name for p in tmp_path.iterdir()} == {referenced, young, "unrelated.txt"}


def test_multipart_stream_stops_before_consuming_oversized_tail():
    header = b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="../../spoof.jpg"\r\n\r\n'
    chunks = iter([header] + [b"x" * 65536] * 100 + [b"\r\n--boundary--\r\n"])
    read = 0
    async def receive():
        nonlocal read
        read += 1
        return {"type": "http.request", "body": next(chunks), "more_body": True}
    request = Request({"type": "http", "headers": [(b"content-type", b"multipart/form-data; boundary=boundary")]}, receive)
    with pytest.raises(OversizedImage):
        asyncio.run(receive_image(request, io.BytesIO()))
    assert read < 100


def test_multipart_truncated_input_is_rejected():
    data = b'--b\r\nContent-Disposition: form-data; name="file"; filename="a.png"\r\n\r\nxxx'
    async def receive():
        return {"type": "http.request", "body": data, "more_body": False}
    request = Request({"type": "http", "headers": [(b"content-type", b"multipart/form-data; boundary=b")]}, receive)
    with pytest.raises(InvalidImage):
        asyncio.run(receive_image(request, io.BytesIO()))
