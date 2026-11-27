from dataclasses import dataclass, field
from typing import BinaryIO

from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header
from starlette.requests import Request

from app.modules.profiles.domain.media import InvalidImage, MAX_IMAGE_BYTES, OversizedImage, UnsupportedImage


@dataclass
class _UploadState:
    parts: int = 0
    size: int = 0
    header_size: int = 0
    header_name: bytes = b""
    header_value: bytes = b""
    headers: dict[bytes, bytes] = field(default_factory=dict)
    done: bool = False
    part_done: bool = False


async def receive_image(request: Request, destination: BinaryIO) -> None:
    content_type, options = parse_options_header(request.headers.get("content-type", ""))
    boundary = options.get(b"boundary")
    if content_type != b"multipart/form-data":
        raise UnsupportedImage("Gunakan multipart/form-data")
    if not boundary or len(boundary) > 200:
        raise InvalidImage("Boundary multipart tidak valid")
    state = _UploadState()

    def begin() -> None:
        state.parts += 1
        if state.parts != 1:
            raise InvalidImage("Kirim tepat satu field file")

    def header_field(data: bytes, start: int, end: int) -> None:
        state.header_size += end - start
        if state.header_size > 8192:
            raise InvalidImage("Header multipart terlalu panjang")
        state.header_name += data[start:end]

    def header_value(data: bytes, start: int, end: int) -> None:
        state.header_size += end - start
        if state.header_size > 8192:
            raise InvalidImage("Header multipart terlalu panjang")
        state.header_value += data[start:end]

    def header_end() -> None:
        key = state.header_name.lower()
        if key in state.headers:
            raise InvalidImage("Header multipart duplikat")
        state.headers[key] = state.header_value
        state.header_name, state.header_value = b"", b""

    def headers_done() -> None:
        disposition, params = parse_options_header(state.headers.get(b"content-disposition", b""))
        if disposition != b"form-data" or params.get(b"name") != b"file" or b"filename" not in params:
            raise InvalidImage("Field file wajib diisi")

    def data_chunk(data: bytes, start: int, end: int) -> None:
        state.size += end - start
        if state.size > MAX_IMAGE_BYTES:
            raise OversizedImage("Ukuran gambar maksimal 5 MiB")
        destination.write(data[start:end])

    def part_end() -> None:
        state.part_done = True

    def end() -> None:
        state.done = True

    parser = MultipartParser(boundary, {
        "on_part_begin": begin, "on_header_field": header_field, "on_header_value": header_value,
        "on_header_end": header_end, "on_headers_finished": headers_done,
        "on_part_data": data_chunk, "on_part_end": part_end, "on_end": end,
    })
    total = 0
    try:
        async for chunk in request.stream():
            total += len(chunk)
            if total > MAX_IMAGE_BYTES + 64 * 1024:
                raise OversizedImage("Request upload terlalu besar")
            for offset in range(0, len(chunk), 64 * 1024):
                parser.write(chunk[offset:offset + 64 * 1024])
        parser.finalize()
    except MultipartParseError as exc:
        raise InvalidImage("Multipart tidak valid") from exc
    if not state.done or not state.part_done or state.parts != 1 or state.size == 0:
        raise InvalidImage("Upload kosong atau multipart tidak lengkap")
    destination.seek(0)
