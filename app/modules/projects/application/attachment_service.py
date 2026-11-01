
import logging
import unicodedata

from pathlib import PureWindowsPath
from typing import BinaryIO, Protocol
from uuid import uuid4

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)
from app.core.unit_of_work import UnitOfWork

from app.modules.projects.domain.attachments import (
    AttachmentRecord,
    AttachmentRepository,
)

from app.modules.projects.infrastructure.attachment_storage import (
    AttachmentStorageError,
)


logger = logging.getLogger(__name__)

# Batas sementara untuk MVP TEMUKARYA.
MAX_PROJECT_ATTACHMENTS = 5
MAX_FILENAME_LENGTH = 255


# ============================================================
# STORAGE INTERFACES
# ============================================================

class StoredFileInfo(Protocol):
    storage_key: str
    mime_type: str
    file_size_bytes: int


class ProjectAttachmentStorage(Protocol):
    """Kontrak storage yang digunakan Application Service."""

    def save(
        self,
        source: BinaryIO,
    ) -> StoredFileInfo:
        ...

    def open(
        self,
        storage_key: str,
    ) -> BinaryIO:
        ...

    def delete(
        self,
        storage_key: str,
    ) -> None:
        ...


# ============================================================
# ATTACHMENT APPLICATION SERVICE
# ============================================================

class ProjectAttachmentService:
    """
    Menangani attachment proyek UMKM.

    Tanggung jawab:
    - Ownership dan status proyek
    - Validasi nama file
    - Batas jumlah attachment
    - Koordinasi storage dan database
    - Commit dan file cleanup

    Tidak menangani HTTP maupun JWT langsung.
    """

    def __init__(
        self,
        repository: AttachmentRepository,
        storage: ProjectAttachmentStorage,
        uow: UnitOfWork,
    ):
        self._repository = repository
        self._storage = storage
        self._uow = uow

    # ========================================================
    # INTERNAL: PROJECT AUTHORIZATION
    # ========================================================

    def _authorize(
        self,
        umkm_id: str,
        project_id: str,
        editable_only: bool = False,
    ) -> None:
        """
        Memastikan proyek milik UMKM yang meminta.

        Operasi tulis mengunci parent project
        menggunakan SELECT FOR UPDATE.
        """

        allowed = self._repository.owns_project(
            project_id=project_id,
            umkm_id=umkm_id,
            editable_only=editable_only,
            lock=editable_only,
        )

        if not allowed:
            raise NotFoundError(
                "Proyek tidak ditemukan atau tidak dapat diubah"
            )

    # ========================================================
    # INTERNAL: FILE NAME VALIDATION
    # ========================================================

    @staticmethod
    def _validate_filename(
        filename: str,
    ) -> str:
        """
        Membersihkan nama file untuk metadata.

        Nama file hanya untuk tampilan.
        Lokasi penyimpanan tetap ditentukan Storage.
        """

        if not isinstance(filename, str):
            raise BadRequestError(
                "Nama file tidak valid"
            )

        # PureWindowsPath menangani slash dan backslash.
        safe_name = PureWindowsPath(
            filename.replace("/", "\\")
        ).name.strip()

        if (
            not safe_name
            or safe_name in (".", "..")
        ):
            raise BadRequestError(
                "Nama file tidak boleh kosong"
            )

        if len(safe_name) > MAX_FILENAME_LENGTH:
            raise BadRequestError(
                "Nama file maksimal 255 karakter"
            )

        # Tolak karakter kontrol dan format tersembunyi,
        # termasuk newline, NUL, dan bidi override.
        if any(
            unicodedata.category(char) in ("Cc", "Cf")
            for char in safe_name
        ):
            raise BadRequestError(
                "Nama file mengandung karakter terlarang"
            )

        return safe_name

    # ========================================================
    # LIST ATTACHMENTS
    # ========================================================

    def list(
        self,
        umkm_id: str,
        project_id: str,
    ) -> list[AttachmentRecord]:
        """Melihat attachment proyek milik UMKM."""

        self._authorize(
            umkm_id=umkm_id,
            project_id=project_id,
        )

        return self._repository.list_by_project(
            project_id=project_id,
        )

    # ========================================================
    # DOWNLOAD ATTACHMENT
    # ========================================================

    def file(
        self,
        umkm_id: str,
        project_id: str,
        attachment_id: str,
    ) -> tuple[AttachmentRecord, BinaryIO]:
        """
        Membuka file setelah pemeriksaan ownership.

        Pemanggil wajib menutup stream setelah selesai.
        """

        self._authorize(
            umkm_id=umkm_id,
            project_id=project_id,
        )

        attachment = self._repository.get_by_id(
            project_id=project_id,
            attachment_id=attachment_id,
        )

        if attachment is None:
            raise NotFoundError(
                "Attachment tidak ditemukan"
            )

        stream = self._storage.open(
            attachment.storage_key
        )

        return attachment, stream

    # ========================================================
    # UPLOAD ATTACHMENT
    # ========================================================

    def upload(
        self,
        umkm_id: str,
        project_id: str,
        filename: str,
        source: BinaryIO,
    ) -> AttachmentRecord:
        """
        Upload attachment dengan compensating cleanup.

        Database dan filesystem bukan satu transaksi.
        Jika metadata gagal disimpan, file baru
        harus dihapus.
        """

        # 1. Pastikan UMKM memiliki proyek dan
        # proyek masih boleh diubah.
        self._authorize(
            umkm_id=umkm_id,
            project_id=project_id,
            editable_only=True,
        )

        # 2. Validasi nama file untuk metadata.
        safe_filename = self._validate_filename(
            filename
        )

        # 3. Ambil attachment sambil mengikuti
        # protokol penguncian transaksi.
        attachments = self._repository.list_by_project(
            project_id=project_id,
            lock=True,
        )

        # 4. Batasi jumlah file per proyek.
        if len(attachments) >= MAX_PROJECT_ATTACHMENTS:
            raise ConflictError(
                "Maksimal 5 attachment per proyek"
            )

        # 5. Storage memvalidasi konten,
        # lalu menyimpan file fisik.
        stored = self._storage.save(source)

        try:
            # 6. Buat metadata dari hasil storage.
            # Jangan menerima storage_key dari klien.
            attachment = AttachmentRecord(
                id=str(uuid4()),
                project_id=project_id,
                original_file_name=safe_filename,
                storage_key=stored.storage_key,
                mime_type=stored.mime_type,
                file_size_bytes=stored.file_size_bytes,
            )

            # 7. Simpan metadata ke database.
            result = self._repository.add(
                attachment
            )

            # 8. Commit melalui UnitOfWork.
            self._uow.commit()

            return result

        except Exception:
            # Bila insert atau commit gagal,
            # kompensasikan file yang sudah disimpan.
            try:
                self._storage.delete(
                    stored.storage_key
                )

            except Exception as cleanup_error:
                logger.exception(
                    "Upload failed; orphan cleanup required: %s",
                    stored.storage_key,
                )

                raise AttachmentStorageError(
                    "Upload gagal; pembersihan file perlu "
                    "penanganan administrator"
                ) from cleanup_error

            # Kegagalan database tetap diteruskan.
            # Session teardown akan melakukan rollback
            # untuk transaksi yang belum berhasil commit.
            raise

    # ========================================================
    # DELETE ATTACHMENT
    # ========================================================

    def delete(
        self,
        umkm_id: str,
        project_id: str,
        attachment_id: str,
    ) -> None:
        """
        Menghapus metadata dahulu, lalu file fisik.

        Jika commit gagal:
        file fisik tetap dipertahankan.

        Jika penghapusan file gagal setelah commit:
        metadata sudah terhapus dan file perlu cleanup.
        """

        # 1. Verifikasi ownership dan status proyek.
        self._authorize(
            umkm_id=umkm_id,
            project_id=project_id,
            editable_only=True,
        )

        # 2. Ambil daftar attachment.
        attachments = self._repository.list_by_project(
            project_id=project_id,
            lock=True,
        )

        # 3. Cari attachment yang diminta.
        attachment = next(
            (
                item
                for item in attachments
                if item.id == attachment_id
            ),
            None,
        )

        if attachment is None:
            raise NotFoundError(
                "Attachment tidak ditemukan"
            )

        # 4. Hapus metadata database.
        deleted = self._repository.delete(
            project_id=project_id,
            attachment_id=attachment_id,
        )

        if not deleted:
            raise NotFoundError(
                "Attachment tidak ditemukan"
            )

        # 5. Commit sebelum menghapus file fisik.
        self._uow.commit()

        # 6. Setelah commit sukses,
        # bersihkan file dari storage.
        try:
            self._storage.delete(
                attachment.storage_key
            )

        except Exception as exc:
            logger.exception(
                "Attachment metadata committed; "
                "orphan cleanup required: %s",
                attachment.storage_key,
            )

            raise AttachmentStorageError(
                "Metadata berhasil dihapus, tetapi "
                "file fisik memerlukan pembersihan"
            ) from exc