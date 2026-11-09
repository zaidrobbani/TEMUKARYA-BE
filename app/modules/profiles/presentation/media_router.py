from functools import wraps

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import ForbiddenError
from app.core.responses import ApiResponse, UtcDateTime, error_body, error_responses, success_response
from app.modules.profiles.domain.media import InvalidImage, MediaError, OversizedImage, StorageFailure, UnsupportedImage
from app.modules.profiles.presentation.auth import AuthenticatedProfileUser, get_authenticated_profile_user
from app.modules.profiles.presentation.media_upload import receive_image
from app.modules.users.domain.entities import UserRole


def media_errors(function):
    @wraps(function)
    async def wrapped(*args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except MediaError as exc:
            status = {OversizedImage: 413, UnsupportedImage: 415, InvalidImage: 422, StorageFailure: 503}.get(type(exc), 503)
            return JSONResponse(error_body(str(exc)), status_code=status)
    return wrapped


class MediaRoute(APIRoute):
    def get_route_handler(self):
        return media_errors(super().get_route_handler())


class MediaResponse(BaseModel):
    id: str
    portfolio_id: str
    mime_type: str
    file_size_bytes: int
    uploaded_at: UtcDateTime
    sort_order: int
    is_cover: bool


class MediaOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_ids: list[str] = Field(max_length=5)


def freelancer(user):
    if user.role != UserRole.FREELANCER:
        raise ForbiddenError("Hanya Freelancer yang dapat mengelola media portfolio")
    return user.user_id


def build_media_router(service_dependency):
    router = APIRouter(prefix="/freelancer/portfolios/{portfolio_id}/media", route_class=MediaRoute)

    @router.post("", status_code=201, response_model=ApiResponse[MediaResponse],
                 responses=error_responses(401, 403, 404, 409, 413, 415, 422, 503), openapi_extra={
        "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
            "type": "object", "required": ["file"], "properties": {"file": {"type": "string", "format": "binary"}},
        }}}},
    })
    async def upload(portfolio_id: str, request: Request,
                     current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
                     service=Depends(service_dependency)):
        owner = freelancer(current_user)
        await run_in_threadpool(service.authorize, owner, portfolio_id, False)
        with service.storage.temporary_upload() as source:
            await receive_image(request, source)
            media = await run_in_threadpool(service.upload, owner, portfolio_id, source)
            return success_response("Media portfolio berhasil diunggah", media)

    @router.get("", response_model=ApiResponse[list[MediaResponse]], responses=error_responses(401, 403, 404))
    def listing(portfolio_id: str, current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
                service=Depends(service_dependency)):
        return success_response("Daftar media portfolio berhasil diambil", service.list(freelancer(current_user), portfolio_id))

    @router.get("/{media_id}/file", responses=error_responses(401, 403, 404, 503))
    def file(portfolio_id: str, media_id: str,
             current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
             service=Depends(service_dependency)):
        item, stream = service.file(freelancer(current_user), portfolio_id, media_id)

        def chunks():
            try:
                while chunk := stream.read(64 * 1024):
                    yield chunk
            finally:
                stream.close()

        return StreamingResponse(chunks(), media_type=item.mime_type, headers={
            "Content-Length": str(item.file_size_bytes), "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff", "Content-Disposition": "inline",
        }, background=BackgroundTask(stream.close))

    @router.patch("/{media_id}/cover", response_model=ApiResponse[list[MediaResponse]],
                  responses=error_responses(401, 403, 404))
    def cover(portfolio_id: str, media_id: str,
              current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
              service=Depends(service_dependency)):
        return success_response("Cover portfolio berhasil diubah", service.cover(freelancer(current_user), portfolio_id, media_id))

    @router.patch("/order", response_model=ApiResponse[list[MediaResponse]],
                  responses=error_responses(401, 403, 404, 422))
    def order(portfolio_id: str, body: MediaOrderRequest,
              current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
              service=Depends(service_dependency)):
        return success_response("Urutan media portfolio berhasil diubah", service.order(freelancer(current_user), portfolio_id, body.media_ids))

    @router.delete("/{media_id}", response_model=ApiResponse[None], responses=error_responses(401, 403, 404, 503))
    def delete(portfolio_id: str, media_id: str,
               current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
               service=Depends(service_dependency)):
        service.delete(freelancer(current_user), portfolio_id, media_id)
        return success_response("Media portfolio berhasil dihapus")

    return router
