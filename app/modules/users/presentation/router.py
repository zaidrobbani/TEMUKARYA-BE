from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.core.responses import ApiResponse, error_responses, success_response
from app.modules.auth.presentation.dependencies import get_current_user
from app.modules.users.application.use_cases import GetProfilePhoto, GetUser, RemoveProfilePhoto, UpdateProfilePhoto
from app.modules.users.domain.avatar import AVATAR_MIME_TYPE
from app.modules.users.domain.entities import User
from app.modules.users.presentation.dependencies import (
    get_profile_photo_use_case,
    get_user_use_case,
    remove_profile_photo_use_case,
    update_profile_photo_use_case,
)
from app.modules.users.presentation.schemas import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.put(
    "/me/photo",
    response_model=ApiResponse[UserResponse],
    responses=error_responses(400, 401, 413, 415, 422, 503),
    summary="Unggah/ganti foto profil (dikompres server ke WebP maks 512 px)",
)
def update_my_photo(
    file: UploadFile = File(..., description="JPG, PNG, atau WebP, maks 2 MB"),
    current_user: User = Depends(get_current_user),
    use_case: UpdateProfilePhoto = Depends(update_profile_photo_use_case),
):
    return success_response("Foto profil berhasil diperbarui", use_case.execute(current_user, file.file))


@router.delete(
    "/me/photo",
    response_model=ApiResponse[UserResponse],
    responses=error_responses(401),
    summary="Hapus foto profil (kembali ke avatar inisial)",
)
def remove_my_photo(
    current_user: User = Depends(get_current_user),
    use_case: RemoveProfilePhoto = Depends(remove_profile_photo_use_case),
):
    return success_response("Foto profil dihapus", use_case.execute(current_user))


@router.get(
    "/{user_id}/photo",
    response_class=StreamingResponse,
    responses={200: {"content": {AVATAR_MIME_TYPE: {}}}} | error_responses(401, 404, 503),
    summary="File foto profil (biner WebP); boleh diakses semua user yang login",
)
def get_user_photo(
    user_id: str,
    _: User = Depends(get_current_user),
    use_case: GetProfilePhoto = Depends(get_profile_photo_use_case),
):
    stream = use_case.execute(user_id)
    return StreamingResponse(
        iter(lambda: stream.read(64 * 1024), b""),
        media_type=AVATAR_MIME_TYPE,
        # URL di profile_image_url berganti tiap foto baru (?v=...), jadi aman di-cache client.
        headers={"Cache-Control": "private, max-age=86400"},
        background=BackgroundTask(stream.close),
    )


@router.get(
    "/{user_id}",
    response_model=ApiResponse[UserResponse],
    responses=error_responses(401, 403, 404),
)
def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    use_case: GetUser = Depends(get_user_use_case),
):
    user = use_case.execute(user_id, requester=current_user)
    return success_response("Data user berhasil diambil", user)
