import os
import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.modules.submissions.domain.repositories import SubmissionFileStorage

_CHUNK = 1024 * 1024


class LocalSubmissionFileStorage(SubmissionFileStorage):
    """File hasil kerja di folder privat (volume Docker). storage_key tidak memakai nama file client."""

    def __init__(self, root: str | Path):
        self._root = Path(root).resolve()

    def _path(self, storage_key: str) -> Path:
        path = (self._root / storage_key).resolve()
        if self._root not in path.parents:
            raise NotFoundError("File tidak ditemukan")
        return path

    def save(self, source: BinaryIO, extension: str) -> str:
        key = f"{uuid4().hex[:2]}/{uuid4().hex}.{extension}"
        target = self._path(key)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            source.seek(0)
            # Tulis ke file sementara lalu rename agar tidak ada file setengah jadi.
            fd, temp = tempfile.mkstemp(dir=target.parent, suffix=".part")
            try:
                with os.fdopen(fd, "wb") as out:
                    shutil.copyfileobj(source, out, _CHUNK)
                os.replace(temp, target)
            except BaseException:
                Path(temp).unlink(missing_ok=True)
                raise
        except OSError as exc:
            raise ServiceUnavailableError("Penyimpanan file tidak tersedia, silakan coba lagi") from exc
        return key

    def open(self, storage_key: str) -> BinaryIO:
        try:
            return self._path(storage_key).open("rb")
        except FileNotFoundError:
            raise NotFoundError("File tidak ditemukan") from None
        except OSError as exc:
            raise ServiceUnavailableError("Penyimpanan file tidak tersedia, silakan coba lagi") from exc

    def delete(self, storage_key: str) -> None:
        try:
            self._path(storage_key).unlink(missing_ok=True)
        except (OSError, NotFoundError):
            pass
