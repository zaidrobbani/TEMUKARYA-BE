import os
import tempfile
from collections.abc import Awaitable, Callable, Iterator
from functools import wraps
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from app.core.database import get_db
from app.core.dependencies import get_uow
from app.core.exceptions import ForbiddenError
from app.core.responses import ApiResponse, SuccessBody, UtcDateTime, error_body, error_responses, success_response
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


class ProjectAttachmentResponse(BaseModel):
    id: str
    project_id: str
    original_file_name: str
    mime_type: str
    file_size_bytes: int
    uploaded_at: UtcDateTime | None = None


RouteHandler = Callable[[Request], Awaitable[Response]]


def attachment_errors(function: RouteHandler) -> RouteHandler:
    @wraps(function)
    async def wrapped(request: Request) -> Response:
        try:
            return await function(request)

        except OversizedAttachment as exc:
            return JSONResponse(
                status_code=413,
                content=error_body(str(exc)),
            )

        except UnsupportedAttachment as exc:
            return JSONResponse(
                status_code=415,
                content=error_body(str(exc)),
            )

        except InvalidAttachment as exc:
            return JSONResponse(
                status_code=422,
                content=error_body(str(exc)),
            )

        except AttachmentStorageError:
            return JSONResponse(
                status_code=503,
                content=error_body(
                    "Layanan penyimpanan attachment tidak tersedia"
                ),
            )

    return wrapped


class AttachmentRoute(APIRoute):
    def get_route_handler(self) -> RouteHandler:
        return attachment_errors(
            super().get_route_handler()
        )


def get_project_attachment_repository(
    db: Session = Depends(get_db),
) -> SqlAlchemyAttachmentRepository:
    return SqlAlchemyAttachmentRepository(db)


def get_project_attachment_storage() -> LocalProjectAttachmentStorage:
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


def require_umkm(
    current_user: AuthenticatedProjectUser,
) -> str:
    if current_user.role != UserRole.UMKM:
        raise ForbiddenError(
            "Hanya UMKM yang dapat mengelola attachment proyek"
        )

    return current_user.user_id


router = APIRouter(
    prefix="/{project_id}/attachments",
    tags=["project-attachments"],
    route_class=AttachmentRoute,
)


@router.post(
    "",
    status_code=201,
    response_model=ApiResponse[ProjectAttachmentResponse],
    responses=error_responses(401, 403, 404, 409, 413, 415, 422, 503),
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
) -> SuccessBody[ProjectAttachmentResponse]:
    umkm_id = require_umkm(current_user)

    await run_in_threadpool(
        service.list,
        umkm_id,
        project_id,
    )

    with tempfile.TemporaryFile(mode="w+b") as source:
        filename = await receive_attachment(
            request,
            source,
        )

        attachment = await run_in_threadpool(
            service.upload,
            umkm_id,
            project_id,
            filename,
            source,
        )
        return success_response("Lampiran project berhasil diunggah", attachment)


@router.get(
    "",
    response_model=ApiResponse[list[ProjectAttachmentResponse]],
    responses=error_responses(401, 403, 404),
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
) -> SuccessBody[list[ProjectAttachmentResponse]]:
    if current_user.role == UserRole.FREELANCER:
        items = service.list_as_freelancer(freelancer_id=current_user.user_id, project_id=project_id)
    else:
        items = service.list(umkm_id=require_umkm(current_user), project_id=project_id)

    return success_response("Daftar lampiran project berhasil diambil", items)


@router.get(
    "/{attachment_id}/file",
    responses=error_responses(401, 403, 404, 503),
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
) -> StreamingResponse:
    if current_user.role == UserRole.FREELANCER:
        attachment, stream = service.file_as_freelancer(
            freelancer_id=current_user.user_id,
            project_id=project_id,
            attachment_id=attachment_id,
        )
    else:
        attachment, stream = service.file(
            umkm_id=require_umkm(current_user),
            project_id=project_id,
            attachment_id=attachment_id,
        )

    def chunks() -> Iterator[bytes]:
        try:
            while True:
                chunk = stream.read(64 * 1024)

                if not chunk:
                    break

                yield chunk

        finally:
            stream.close()

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


@router.delete(
    "/{attachment_id}",
    response_model=ApiResponse[None],
    responses=error_responses(401, 403, 404, 409, 503),
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
) -> SuccessBody[None]:
    umkm_id = require_umkm(current_user)

    service.delete(
        umkm_id=umkm_id,
        project_id=project_id,
        attachment_id=attachment_id,
    )

    return success_response("Lampiran project berhasil dihapus")
