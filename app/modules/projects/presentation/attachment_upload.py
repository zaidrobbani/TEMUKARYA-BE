from dataclasses import dataclass, field
from typing import BinaryIO

from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header
from starlette.requests import Request

from app.modules.projects.infrastructure.attachment_storage import (
    InvalidAttachment,
    MAX_ATTACHMENT_BYTES,
    OversizedAttachment,
    UnsupportedAttachment,
)

CHUNK_SIZE = 64 * 1024
MAX_MULTIPART_OVERHEAD = 64 * 1024
MAX_HEADER_BYTES = 8192
MAX_BOUNDARY_BYTES = 200


@dataclass
class _UploadState:
    parts: int = 0
    header_bytes: int = 0
    header_field: bytearray = field(default_factory=bytearray)
    header_value: bytearray = field(default_factory=bytearray)
    headers: dict[bytes, bytes] = field(default_factory=dict)
    filename: str | None = None
    file_size: int = 0
    part_done: bool = False
    done: bool = False


async def receive_attachment(request: Request, destination: BinaryIO) -> str:
    content_type, parameters = parse_options_header(request.headers.get("content-type", ""))
    boundary = parameters.get(b"boundary")
    if content_type != b"multipart/form-data":
        raise UnsupportedAttachment("Gunakan multipart/form-data")
    if not boundary or len(boundary) > MAX_BOUNDARY_BYTES or b"\r" in boundary or b"\n" in boundary:
        raise InvalidAttachment("Boundary multipart tidak valid")

    state = _UploadState()

    def on_part_begin() -> None:
        state.parts += 1
        if state.parts != 1:
            raise InvalidAttachment("Kirim tepat satu field file")
        state.headers = {}

    def on_header_field(data: bytes, start: int, end: int) -> None:
        state.header_bytes += end - start
        if state.header_bytes > MAX_HEADER_BYTES:
            raise InvalidAttachment("Header multipart terlalu panjang")
        state.header_field.extend(data[start:end])

    def on_header_value(data: bytes, start: int, end: int) -> None:
        state.header_bytes += end - start
        if state.header_bytes > MAX_HEADER_BYTES:
            raise InvalidAttachment("Header multipart terlalu panjang")
        state.header_value.extend(data[start:end])

    def on_header_end() -> None:
        key = bytes(state.header_field).lower()
        if key in state.headers:
            raise InvalidAttachment("Header multipart duplikat")
        state.headers[key] = bytes(state.header_value)
        state.header_field.clear()
        state.header_value.clear()

    def on_headers_finished() -> None:
        disposition, options = parse_options_header(state.headers.get(b"content-disposition", b""))
        raw_filename = options.get(b"filename")
        if disposition != b"form-data" or options.get(b"name") != b"file" or raw_filename is None:
            raise InvalidAttachment("Field file wajib diisi")
        try:
            state.filename = raw_filename.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidAttachment("Nama file harus menggunakan UTF-8") from exc

    def on_part_data(data: bytes, start: int, end: int) -> None:
        state.file_size += end - start
        if state.file_size > MAX_ATTACHMENT_BYTES:
            raise OversizedAttachment("Ukuran attachment maksimal 5 MiB")
        destination.write(data[start:end])

    def on_part_end() -> None:
        state.part_done = True

    def on_end() -> None:
        state.done = True

    parser = MultipartParser(
        boundary,
        {
            "on_part_begin": on_part_begin,
            "on_header_field": on_header_field,
            "on_header_value": on_header_value,
            "on_header_end": on_header_end,
            "on_headers_finished": on_headers_finished,
            "on_part_data": on_part_data,
            "on_part_end": on_part_end,
            "on_end": on_end,
        },
    )

    total_request_bytes = 0
    try:
        async for chunk in request.stream():
            total_request_bytes += len(chunk)
            if total_request_bytes > MAX_ATTACHMENT_BYTES + MAX_MULTIPART_OVERHEAD:
                raise OversizedAttachment("Request upload terlalu besar")
            for offset in range(0, len(chunk), CHUNK_SIZE):
                parser.write(chunk[offset:offset + CHUNK_SIZE])
        parser.finalize()
    except (MultipartParseError, ValueError) as exc:
        raise InvalidAttachment("Multipart tidak valid") from exc

    if state.parts != 1 or not state.part_done or not state.done or state.file_size == 0 or state.filename is None:
        raise InvalidAttachment("Upload kosong atau multipart tidak lengkap")

    destination.seek(0)
    return state.filename
