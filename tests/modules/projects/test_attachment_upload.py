
from io import BytesIO

import pytest

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.modules.projects.presentation.attachment_upload import (
    receive_attachment,
)

from app.modules.projects.infrastructure.attachment_storage import (
    InvalidAttachment,
    OversizedAttachment,
    UnsupportedAttachment,
)


# ============================================================
# TEST APPLICATION
# ============================================================

@pytest.fixture
def client():

    app = FastAPI()

    @app.post("/upload-test")
    async def upload_test(request: Request):

        destination = BytesIO()

        try:
            filename = await receive_attachment(
                request,
                destination,
            )

            content = destination.getvalue()

            return {
                "filename": filename,
                "size": len(content),
                "content": content.decode(
                    "latin-1"
                ),
            }

        except OversizedAttachment as exc:
            return JSONResponse(
                {"detail": str(exc)},
                status_code=413,
            )

        except UnsupportedAttachment as exc:
            return JSONResponse(
                {"detail": str(exc)},
                status_code=415,
            )

        except InvalidAttachment as exc:
            return JSONResponse(
                {"detail": str(exc)},
                status_code=422,
            )

        finally:
            destination.close()

    with TestClient(app) as test_client:
        yield test_client


# ============================================================
# MULTIPART TEST HELPERS
# ============================================================

BOUNDARY = b"testboundary"

CONTENT_TYPE = {
    "Content-Type": (
        "multipart/form-data; boundary=testboundary"
    ),
}

FILE_HEADERS = [
    (
        b'Content-Disposition: form-data; '
        b'name="file"; filename="test.pdf"'
    ),
    b"Content-Type: application/pdf",
]


def build_multipart(
    parts,
    ending=True,
):
    body = b""

    for headers, data in parts:
        body += b"--" + BOUNDARY + b"\r\n"
        body += b"\r\n".join(headers)
        body += b"\r\n\r\n"
        body += data
        body += b"\r\n"

    if ending:
        body += b"--" + BOUNDARY + b"--\r\n"

    return body


def send_multipart(client, body):
    return client.post(
        "/upload-test",
        content=body,
        headers=CONTENT_TYPE,
    )


# ============================================================
# TEST 1: VALID MULTIPART
# ============================================================

def test_valid_single_file_upload(client):

    content = b"%PDF-1.4\nExample PDF data"

    response = send_multipart(
        client,
        build_multipart([
            (FILE_HEADERS, content)
        ]),
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "test.pdf"
    assert response.json()["size"] == len(content)


# ============================================================
# TEST 2: OVERSIZED FILE
# ============================================================

def test_rejects_oversized_upload(client):

    content = b"X" * (
        5 * 1024 * 1024 + 1
    )

    response = send_multipart(
        client,
        build_multipart([
            (FILE_HEADERS, content)
        ]),
    )

    assert response.status_code == 413


# ============================================================
# TEST 3: EMPTY FILE
# ============================================================

def test_rejects_empty_file(client):

    response = send_multipart(
        client,
        build_multipart([
            (FILE_HEADERS, b"")
        ]),
    )

    assert response.status_code == 422


# ============================================================
# TEST 4: MULTIPLE FILES
# ============================================================

def test_rejects_multiple_files(client):

    response = send_multipart(
        client,
        build_multipart([
            (FILE_HEADERS, b"First"),
            (FILE_HEADERS, b"Second"),
        ]),
    )

    assert response.status_code == 422


# ============================================================
# TEST 5: WRONG FIELD NAME
# ============================================================

def test_rejects_wrong_field_name(client):

    headers = [
        (
            b'Content-Disposition: form-data; '
            b'name="other"; filename="test.pdf"'
        )
    ]

    response = send_multipart(
        client,
        build_multipart([
            (headers, b"Test")
        ]),
    )

    assert response.status_code == 422


# ============================================================
# TEST 6: MISSING FILENAME
# ============================================================

def test_rejects_missing_filename(client):

    headers = [
        (
            b'Content-Disposition: form-data; '
            b'name="file"'
        )
    ]

    response = send_multipart(
        client,
        build_multipart([
            (headers, b"Test")
        ]),
    )

    assert response.status_code == 422


# ============================================================
# TEST 7: WRONG CONTENT TYPE
# ============================================================

def test_rejects_wrong_content_type(client):

    response = client.post(
        "/upload-test",
        content=b'{"file":"test.pdf"}',
        headers={
            "Content-Type": "application/json"
        },
    )

    assert response.status_code == 415


# ============================================================
# TEST 8: OVERSIZED MULTIPART HEADER
# ============================================================

def test_rejects_oversized_header(client):

    headers = FILE_HEADERS + [
        b"X-Test: " + b"A" * 9000
    ]

    response = send_multipart(
        client,
        build_multipart([
            (headers, b"Test")
        ]),
    )

    assert response.status_code == 422


# ============================================================
# TEST 9: INCOMPLETE MULTIPART
# ============================================================

def test_rejects_truncated_multipart(client):

    response = send_multipart(
        client,
        build_multipart(
            [(FILE_HEADERS, b"Test")],
            ending=False,
        ),
    )

    assert response.status_code == 422