
from io import BytesIO

import pytest

from PIL import Image, PngImagePlugin
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject

from app.modules.projects.infrastructure.attachment_storage import (
    AttachmentStorageError,
    InvalidAttachment,
    LocalProjectAttachmentStorage,
    MAX_ATTACHMENT_BYTES,
    OversizedAttachment,
    UnsupportedAttachment,
)


# ============================================================
# TEST FIXTURE
# ============================================================

@pytest.fixture
def storage(tmp_path):
    """Penyimpanan sementara khusus pengujian."""

    return LocalProjectAttachmentStorage(
        tmp_path / "projects"
    )


# ============================================================
# VALID TEST FILE FACTORIES
# ============================================================

def valid_pdf():
    """Buat PDF asli dengan satu halaman."""

    writer = PdfWriter()

    writer.add_blank_page(
        width=200,
        height=200,
    )

    content = BytesIO()
    writer.write(content)

    return content.getvalue()


def valid_png(with_metadata=False):
    """Buat PNG asli dengan optional metadata."""

    content = BytesIO()

    with Image.new(
        "RGB",
        (12, 10),
        "red",
    ) as picture:

        if with_metadata:
            extra = PngImagePlugin.PngInfo()

            extra.add_text(
                "Comment",
                "sensitive metadata",
            )

            picture.save(
                content,
                format="PNG",
                pnginfo=extra,
            )

        else:
            picture.save(
                content,
                format="PNG",
            )

    return content.getvalue()


# ============================================================
# PDF STORAGE TESTS
# ============================================================

def test_save_and_read_real_pdf(storage):

    content = valid_pdf()

    saved = storage.save(
        BytesIO(content)
    )

    assert saved.mime_type == "application/pdf"
    assert saved.file_size_bytes == len(content)
    assert saved.storage_key.endswith(".pdf")

    with storage.open(saved.storage_key) as stream:
        assert stream.read() == content


def test_storage_key_uses_uuid(storage):

    first = storage.save(
        BytesIO(valid_pdf())
    )

    second = storage.save(
        BytesIO(valid_pdf())
    )

    assert first.storage_key != second.storage_key


def test_rejects_fake_pdf_header(storage):

    fake_pdf = (
        b"%PDF-1.4\n"
        b"This is not a PDF\n"
        b"%%EOF"
    )

    with pytest.raises(InvalidAttachment):
        storage.save(
            BytesIO(fake_pdf)
        )

    assert list(storage.root.iterdir()) == []


def test_rejects_truncated_pdf(storage):

    content = valid_pdf()

    with pytest.raises(InvalidAttachment):
        storage.save(
            BytesIO(content[:-20])
        )


def test_rejects_pdf_with_active_action(storage):

    writer = PdfWriter()

    writer.add_blank_page(
        width=200,
        height=200,
    )

    writer._root_object.update({
        NameObject("/OpenAction"): DictionaryObject()
    })

    content = BytesIO()
    writer.write(content)

    with pytest.raises(InvalidAttachment):
        storage.save(
            BytesIO(content.getvalue())
        )


# ============================================================
# IMAGE VALIDATION TESTS
# ============================================================

def test_valid_png_is_reencoded_without_metadata(storage):

    original = valid_png(
        with_metadata=True
    )

    saved = storage.save(
        BytesIO(original)
    )

    assert saved.mime_type == "image/png"
    assert saved.storage_key.endswith(".png")

    with storage.open(saved.storage_key) as stream:
        with Image.open(stream) as picture:

            picture.load()

            assert picture.size == (12, 10)

            # Metadata asal harus hilang.
            assert "Comment" not in picture.info


def test_rejects_corrupt_png(storage):

    corrupt_png = (
        b"\x89PNG\r\n\x1a\n"
        b"not a png"
    )

    with pytest.raises(InvalidAttachment):
        storage.save(
            BytesIO(corrupt_png)
        )

    assert list(storage.root.iterdir()) == []


def test_rejects_image_over_dimension_limit(storage):

    content = BytesIO()

    with Image.new(
        "RGB",
        (4097, 1),
        "blue",
    ) as picture:

        picture.save(
            content,
            format="PNG",
        )

    with pytest.raises(InvalidAttachment):
        storage.save(
            BytesIO(content.getvalue())
        )


# ============================================================
# FILE SIZE & FORMAT TESTS
# ============================================================

def test_rejects_empty_file(storage):

    with pytest.raises(InvalidAttachment):
        storage.save(
            BytesIO(b"")
        )


def test_rejects_unsupported_file(storage):

    with pytest.raises(UnsupportedAttachment):
        storage.save(
            BytesIO(
                b"<html>Fake document</html>"
            )
        )


def test_rejects_oversized_file(storage):

    content = (
        b"%PDF-1.4\n"
        + b"A" * MAX_ATTACHMENT_BYTES
    )

    with pytest.raises(OversizedAttachment):
        storage.save(
            BytesIO(content)
        )


# ============================================================
# PATH SECURITY TESTS
# ============================================================

def test_rejects_path_traversal(storage):

    with pytest.raises(AttachmentStorageError):
        storage.open(
            "../../secrets.txt"
        )


def test_rejects_invalid_key(storage):

    with pytest.raises(AttachmentStorageError):
        storage.delete(
            "../../foo.pdf"
        )


# ============================================================
# DELETE & CLEANUP TESTS
# ============================================================

def test_delete_attachment(storage):

    saved = storage.save(
        BytesIO(valid_pdf())
    )

    path = (
        storage.root
        / saved.storage_key
    )

    assert path.exists()

    storage.delete(
        saved.storage_key
    )

    assert not path.exists()


def test_failed_upload_removes_temporary_file(storage):

    with pytest.raises(UnsupportedAttachment):
        storage.save(
            BytesIO(
                b"Invalid file content"
            )
        )

    assert list(storage.root.iterdir()) == []