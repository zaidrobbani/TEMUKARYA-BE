
import os
import tempfile

from datetime import datetime
from functools import wraps
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from app.core.database import get_db
from app.core.dependencies import get_uow
from app.core.exceptions import ForbiddenError
from app.core.unit_of_work import UnitOfWork

from app.modules.users.domain.entities import UserRole

from app.modules.projects.application.attachment_service import (
    ProjectAttachmentService,
)

from app.modules.projects.infrastructure.attachment_repository import (
    SqlAlchemyAttachmentRepository,
)

from app.modules.projects.infrastructure.attachment_storage import (
    AttachmentStorageError,
    InvalidAttachment,
    LocalProjectAttachmentStorage,
    OversizedAttachment,
    UnsupportedAttachment,
)

from app.modules.projects.presentation.attachment_upload import (
    receive_attachment,
)

from app.modules.projects.presentation.dependencies import (
    AuthenticatedProjectUser,
    get_authenticated_project_user,
)


# ============================================================
# RESPONSE SCHEMA
# ============================================================

class ProjectAttachmentResponse(BaseModel):
    id: str
    project_id: str
    original_file_name: str
    mime_type: str
    file_size_bytes: int
    uploaded_at: datetime | None = None


# ============================================================
# ATTACHMENT ERROR HANDLING
# ============================================================

def attachment_errors(function):
    """
    Mengubah error storage menjadi HTTP response.

    Error aplikasi seperti NotFoundError tetap
    ditangani global error handler TEMUKARYA.
    """

    @wraps(function)
    async def wrapped(*args, **kwargs):
        try:
            return await function(*args, **kwargs)

        except OversizedAttachment as exc:
            return JSONResponse(
                status_code=413,
                content={"detail": str(exc)},
            )

        except UnsupportedAttachment as exc:
            return JSONResponse(
                status_code=415,
                content={"detail": str(exc)},
            )

        except InvalidAttachment as exc:
            return JSONResponse(
                status_code=422,
                content={"detail": str(exc)},
            )

        except AttachmentStorageError:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Layanan penyimpanan attachment tidak tersedia"
                },
            )

    return wrapped


class AttachmentRoute(APIRoute):
    def get_route_handler(self):
        return attachment_errors(
            super().get_route_handler()
        )


# ============================================================
# DEPENDENCY INJECTION
# ============================================================

def get_project_attachment_repository(
    db: Session = Depends(get_db),
) -> SqlAlchemyAttachmentRepository:
    return SqlAlchemyAttachmentRepository(db)


def get_project_attachment_storage() -> LocalProjectAttachmentStorage:
    """
    Folder development:
        <project-root>/storage/projects

    Folder Docker dapat diatur menggunakan:
        PROJECT_ATTACHMENT_STORAGE_ROOT

    Folder harus disimpan di private persistent volume.
    """

    configured_root = os.getenv(
        "PROJECT_ATTACHMENT_STORAGE_ROOT"
    )

    if configured_root:
        root = Path(configured_root)
    else:
        root = (
            Path.cwd().resolve()
            / "storage"
            / "projects"
        )

    return LocalProjectAttachmentStorage(root)


def get_project_attachment_service(
    repository: SqlAlchemyAttachmentRepository = Depends(
        get_project_attachment_repository
    ),
    storage: LocalProjectAttachmentStorage = Depends(
        get_project_attachment_storage
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> ProjectAttachmentService:
    return ProjectAttachmentService(
        repository=repository,
        storage=storage,
        uow=uow,
    )


# ============================================================
# ROLE AUTHORIZATION
# ============================================================

def require_umkm(
    current_user: AuthenticatedProjectUser,
) -> str:
    if current_user.role != UserRole.UMKM:
        raise ForbiddenError(
            "Hanya UMKM yang dapat mengelola attachment proyek"
        )

    return current_user.user_id


# ============================================================
# ATTACHMENT ROUTER
# ============================================================

router = APIRouter(
    prefix="/{project_id}/attachments",
    tags=["project-attachments"],
    route_class=AttachmentRoute,
)


# ============================================================
# 1. UPLOAD ATTACHMENT
# ============================================================

@router.post(
    "",
    status_code=201,
    response_model=ProjectAttachmentResponse,
    summary="Upload Project Attachment",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "properties": {
                            "file": {
                                "type": "string",
                                "format": "binary",
                            }
                        },
                    }
                }
            },
        }
    },
)
async def upload_project_attachment(
    project_id: str,
    request: Request,
    current_user: AuthenticatedProjectUser = Depends(
        get_authenticated_project_user
    ),
    service: ProjectAttachmentService = Depends(
        get_project_attachment_service
    ),
):
    # 1. Verifikasi role terlebih dahulu.
    umkm_id = require_umkm(current_user)

    # 2. Periksa kepemilikan sebelum membaca body request.
    # Service.upload akan mengecek lagi status proyek
    # dan mengambil lock saat operasi tulis.
    await run_in_threadpool(
        service.list,
        umkm_id,
        project_id,
    )

    # 3. Simpan request multipart di temporary stream.
    # File belum menjadi attachment permanen.
    with tempfile.TemporaryFile(mode="w+b") as source:

        filename = await receive_attachment(
            request,
            source,
        )

        # 4. Jalankan validasi file, storage,
        # metadata database, dan commit di worker.
        return await run_in_threadpool(
            service.upload,
            umkm_id,
            project_id,
            filename,
            source,
        )


# ============================================================
# 2. LIST ATTACHMENTS
# ============================================================

@router.get(
    "",
    response_model=list[ProjectAttachmentResponse],
    summary="List Project Attachments",
)
def list_project_attachments(
    project_id: str,
    current_user: AuthenticatedProjectUser = Depends(
        get_authenticated_project_user
    ),
    service: ProjectAttachmentService = Depends(
        get_project_attachment_service
    ),
):
    umkm_id = require_umkm(current_user)

    return service.list(
        umkm_id=umkm_id,
        project_id=project_id,
    )


# ============================================================
# 3. DOWNLOAD ATTACHMENT
# ============================================================

@router.get(
    "/{attachment_id}/file",
    summary="Download Project Attachment",
)
def download_project_attachment(
    project_id: str,
    attachment_id: str,
    current_user: AuthenticatedProjectUser = Depends(
        get_authenticated_project_user
    ),
    service: ProjectAttachmentService = Depends(
        get_project_attachment_service
    ),
):
    umkm_id = require_umkm(current_user)

    # Service memeriksa kepemilikan sebelum
    # membuka stream file fisik.
    attachment, stream = service.file(
        umkm_id=umkm_id,
        project_id=project_id,
        attachment_id=attachment_id,
    )

    def chunks():
        try:
            while True:
                chunk = stream.read(64 * 1024)

                if not chunk:
                    break

                yield chunk

        finally:
            stream.close()

    # Gunakan nama download tetap agar filename
    # dari pengguna tidak masuk ke HTTP header.
    # application/octet-stream memaksa download
    # dan tidak mengandalkan tipe konten klien.
    return StreamingResponse(
        chunks(),
        media_type="application/octet-stream",
        headers={
            "Content-Length": str(
                attachment.file_size_bytes
            ),
            "Content-Disposition": (
                'attachment; filename="project-attachment"'
            ),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
        background=BackgroundTask(stream.close),
    )


# ============================================================
# 4. DELETE ATTACHMENT
# ============================================================

@router.delete(
    "/{attachment_id}",
    status_code=204,
    response_class=Response,
    summary="Delete Project Attachment",
)
def delete_project_attachment(
    project_id: str,
    attachment_id: str,
    current_user: AuthenticatedProjectUser = Depends(
        get_authenticated_project_user
    ),
    service: ProjectAttachmentService = Depends(
        get_project_attachment_service
    ),
) -> Response:
    umkm_id = require_umkm(current_user)

    service.delete(
        umkm_id=umkm_id,
        project_id=project_id,
        attachment_id=attachment_id,
    )

    return Response(status_code=204)