
import logging
import os
import re
import tempfile
import warnings

from dataclasses import dataclass
from pathlib import Path
from threading import BoundedSemaphore
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader


# ============================================================
# CONFIGURATION
# ============================================================

logger = logging.getLogger(__name__)

MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 4096
MAX_PDF_PAGES = 50
CHUNK_SIZE = 64 * 1024

IMAGE_DECODER_SLOT = BoundedSemaphore(1)

KEY_PATTERN = re.compile(
    r"[0-9a-f]{32}\.(?:pdf|jpg|png|webp)\Z"
)


# ============================================================
# CUSTOM EXCEPTIONS
# ============================================================

class AttachmentStorageError(Exception):
    """Kesalahan pada penyimpanan lokal attachment."""


class InvalidAttachment(AttachmentStorageError):
    """Attachment kosong, rusak, atau kontennya berisiko."""


class OversizedAttachment(AttachmentStorageError):
    """Ukuran attachment melampaui batas."""


class UnsupportedAttachment(AttachmentStorageError):
    """Format attachment tidak didukung."""


# ============================================================
# STORED ATTACHMENT ENTITY
# ============================================================

@dataclass(frozen=True)
class StoredAttachment:
    storage_key: str
    mime_type: str
    file_size_bytes: int


# ============================================================
# FILE TYPE DETECTION
# ============================================================

def detect_file_type(header: bytes) -> tuple[str, str]:
    """
    Deteksi awal format menggunakan signature file.

    Tidak mempercayai ekstensi atau MIME dari klien.
    """

    if header.startswith(b"%PDF-"):
        return "pdf", "application/pdf"

    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"

    if header.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"

    if (
        header[:4] == b"RIFF"
        and header[8:12] == b"WEBP"
    ):
        return "webp", "image/webp"

    raise UnsupportedAttachment(
        "Hanya PDF, JPEG, PNG, dan WebP yang didukung"
    )


# ============================================================
# LOCAL ATTACHMENT STORAGE
# ============================================================

class LocalProjectAttachmentStorage:
    """
    Penyimpanan private untuk attachment proyek.

    Direktori storage harus hanya dapat ditulis
    oleh aplikasi dan administrator tepercaya.
    """

    def __init__(self, root: str | Path):
        root_path = Path(root)

        if (
            not root_path.is_absolute()
            or root_path.is_symlink()
        ):
            raise AttachmentStorageError(
                "Storage root harus path absolut tanpa symlink"
            )

        self.root = root_path.resolve()

        try:
            self.root.mkdir(
                parents=True,
                exist_ok=True,
            )

        except OSError as exc:
            raise AttachmentStorageError(
                "Direktori storage tidak tersedia"
            ) from exc

    # ========================================================
    # SAFE STORAGE PATH
    # ========================================================

    def _get_path(self, storage_key: str) -> Path:
        """
        Storage key hanya boleh berupa UUID acak
        dan ekstensi yang telah ditentukan.
        """

        if (
            not isinstance(storage_key, str)
            or not KEY_PATTERN.fullmatch(storage_key)
        ):
            raise AttachmentStorageError(
                "Storage key tidak valid"
            )

        path = self.root / storage_key

        if path.is_symlink():
            raise AttachmentStorageError(
                "Symlink tidak diperbolehkan"
            )

        return path

    # ========================================================
    # PDF VALIDATION
    # ========================================================

    @staticmethod
    def _validate_pdf(
        path: Path,
        size: int,
    ) -> None:
        """
        Memvalidasi struktur dasar dokumen PDF.

        Pemeriksaan ini bukan antivirus dan
        bukan sanitasi PDF menyeluruh.
        """

        try:
            with path.open("rb") as stream:

                # 1. Periksa versi header PDF.
                head = stream.read(8)

                if not re.fullmatch(
                    rb"%PDF-[12]\.[0-9]",
                    head,
                ):
                    raise InvalidAttachment(
                        "Header versi PDF tidak valid"
                    )

                # 2. Periksa penanda akhir PDF.
                stream.seek(max(0, size - 2048))

                if not stream.read().rstrip().endswith(
                    b"%%EOF"
                ):
                    raise InvalidAttachment(
                        "PDF tidak memiliki penanda akhir valid"
                    )

                # 3. Parse struktur PDF dengan pypdf.
                stream.seek(0)

                reader = PdfReader(
                    stream,
                    strict=True,
                )

                # 4. Tolak PDF terenkripsi.
                if reader.is_encrypted:
                    raise InvalidAttachment(
                        "PDF terenkripsi tidak didukung"
                    )

                # 5. Batasi jumlah halaman.
                page_count = len(reader.pages)

                if not 1 <= page_count <= MAX_PDF_PAGES:
                    raise InvalidAttachment(
                        "PDF harus memiliki 1 hingga 50 halaman"
                    )

                # 6. Tolak fitur aktif umum pada catalog.
                root = reader.trailer["/Root"]

                forbidden_catalog_keys = (
                    "/OpenAction",
                    "/AA",
                    "/Names",
                    "/AcroForm",
                )

                if any(
                    key in root
                    for key in forbidden_catalog_keys
                ):
                    raise InvalidAttachment(
                        "PDF dengan konten aktif/form tidak didukung"
                    )

                # 7. Tolak anotasi dan aksi pada halaman.
                for page in reader.pages:
                    if (
                        "/Annots" in page
                        or "/AA" in page
                    ):
                        raise InvalidAttachment(
                            "PDF dengan anotasi/aksi tidak didukung"
                        )

        except InvalidAttachment:
            raise

        except Exception as exc:
            logger.warning(
                "PDF validation failed (%s)",
                type(exc).__name__,
            )

            raise InvalidAttachment(
                "PDF rusak atau tidak dapat dibaca"
            ) from exc

    # ========================================================
    # IMAGE VALIDATION & NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_image(
        source_path: Path,
        output_path: Path,
        extension: str,
    ) -> int:
        """
        Validasi dan normalisasi gambar.

        Gambar didekode lalu disimpan ulang dari
        pixel baru untuk membuang metadata asal.
        """

        expected_format = {
            "jpg": "JPEG",
            "png": "PNG",
            "webp": "WEBP",
        }[extension]

        # Batasi decoder per proses.
        with IMAGE_DECODER_SLOT:
            try:

                with warnings.catch_warnings():
                    warnings.simplefilter(
                        "error",
                        Image.DecompressionBombWarning,
                    )

                    # 1. Verifikasi struktur gambar.
                    with Image.open(
                        source_path
                    ) as picture:

                        if picture.format != expected_format:
                            raise InvalidAttachment(
                                "Format gambar tidak konsisten"
                            )

                        width, height = picture.size

                        if not (
                            0 < width <= MAX_IMAGE_DIMENSION
                            and 0 < height <= MAX_IMAGE_DIMENSION
                        ):
                            raise InvalidAttachment(
                                "Dimensi gambar maksimal 4096x4096"
                            )

                        if getattr(
                            picture,
                            "n_frames",
                            1,
                        ) != 1:
                            raise InvalidAttachment(
                                "Gambar animasi tidak didukung"
                            )

                        picture.verify()

                    # 2. Buka ulang dan decode gambar.
                    with Image.open(
                        source_path
                    ) as picture:

                        picture.load()

                        oriented = ImageOps.exif_transpose(
                            picture
                        )

                        mode = (
                            "RGB"
                            if extension == "jpg"
                            else "RGBA"
                        )

                        if (
                            extension == "webp"
                            and "A" not in picture.getbands()
                        ):
                            mode = "RGB"

                        # 3. Buat pixel baru tanpa metadata.
                        with oriented.convert(
                            mode
                        ) as converted:

                            with Image.frombytes(
                                mode,
                                converted.size,
                                converted.tobytes(),
                            ) as clean:

                                # 4. Simpan gambar hasil normalisasi.
                                with output_path.open(
                                    "w+b"
                                ) as output:

                                    clean.save(
                                        output,
                                        format=expected_format,
                                    )

                                    output.flush()
                                    os.fsync(
                                        output.fileno()
                                    )

                                    size = output.tell()

                # 5. Periksa ukuran hasil normalisasi.
                if size > MAX_ATTACHMENT_BYTES:
                    raise OversizedAttachment(
                        "Hasil normalisasi melebihi 5 MiB"
                    )

                return size

            except (
                InvalidAttachment,
                OversizedAttachment,
            ):
                raise

            except (
                Image.DecompressionBombError,
                Image.DecompressionBombWarning,
                UnidentifiedImageError,
                OSError,
                SyntaxError,
                ValueError,
                EOFError,
            ) as exc:
                raise InvalidAttachment(
                    "Gambar rusak atau tidak valid"
                ) from exc

    # ========================================================
    # SAVE ATTACHMENT
    # ========================================================

    def save(
        self,
        source,
    ) -> StoredAttachment:
        """
        Membaca stream secara terbatas,
        memvalidasi file, lalu menyimpannya
        dengan storage key acak.

        Filename dan Content-Type klien
        tidak digunakan.
        """

        paths_to_cleanup: list[Path] = []

        try:

            # =================================================
            # 1. STAGE FILE
            # =================================================

            with tempfile.NamedTemporaryFile(
                prefix=".upload-",
                dir=self.root,
                delete=False,
            ) as staged:

                source_path = Path(staged.name)
                paths_to_cleanup.append(source_path)

                size = 0

                while True:
                    chunk = source.read(CHUNK_SIZE)

                    if not chunk:
                        break

                    if not isinstance(chunk, bytes):
                        raise InvalidAttachment(
                            "File harus berupa binary stream"
                        )

                    size += len(chunk)

                    if size > MAX_ATTACHMENT_BYTES:
                        raise OversizedAttachment(
                            "Ukuran attachment maksimal 5 MiB"
                        )

                    staged.write(chunk)

                if size == 0:
                    raise InvalidAttachment(
                        "File attachment tidak boleh kosong"
                    )

                staged.flush()
                os.fsync(staged.fileno())

                staged.seek(0)

                extension, mime_type = detect_file_type(
                    staged.read(16)
                )

            # =================================================
            # 2. VALIDATE PDF OR NORMALIZE IMAGE
            # =================================================

            if extension == "pdf":

                self._validate_pdf(
                    source_path,
                    size,
                )

                ready_path = source_path
                final_size = size

            else:

                with tempfile.NamedTemporaryFile(
                    prefix=".normalized-",
                    dir=self.root,
                    delete=False,
                ) as output:

                    ready_path = Path(output.name)
                    paths_to_cleanup.append(
                        ready_path
                    )

                final_size = self._normalize_image(
                    source_path,
                    ready_path,
                    extension,
                )

            # =================================================
            # 3. GENERATE RANDOM STORAGE KEY
            # =================================================

            storage_key = (
                f"{uuid4().hex}.{extension}"
            )

            destination = self._get_path(
                storage_key
            )

            # =================================================
            # 4. ATOMIC FILE REPLACEMENT
            # =================================================

            os.replace(
                ready_path,
                destination,
            )

            paths_to_cleanup.remove(
                ready_path
            )

            return StoredAttachment(
                storage_key=storage_key,
                mime_type=mime_type,
                file_size_bytes=final_size,
            )

        except AttachmentStorageError:
            raise

        except (
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            raise AttachmentStorageError(
                "Gagal menyimpan attachment"
            ) from exc

        finally:
            # Bersihkan file sementara saat berhasil
            # maupun saat validasi gagal.
            for path in paths_to_cleanup:
                try:
                    path.unlink(
                        missing_ok=True
                    )

                except OSError:
                    logger.exception(
                        "Cleanup temporary attachment failed: %s",
                        path,
                    )

    # ========================================================
    # OPEN ATTACHMENT
    # ========================================================

    def open(self, storage_key: str):
        """Membuka attachment menggunakan storage key."""

        path = self._get_path(
            storage_key
        )

        try:
            flags = (
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
            )

            descriptor = os.open(
                path,
                flags,
            )

            return os.fdopen(
                descriptor,
                "rb",
            )

        except OSError as exc:
            raise AttachmentStorageError(
                "File attachment tidak tersedia"
            ) from exc

    # ========================================================
    # DELETE ATTACHMENT
    # ========================================================

    def delete(
        self,
        storage_key: str,
    ) -> None:
        """Menghapus attachment berdasarkan storage key."""

        try:
            self._get_path(
                storage_key
            ).unlink(
                missing_ok=True
            )

        except OSError as exc:
            raise AttachmentStorageError(
                "Gagal menghapus attachment"
            ) from exc