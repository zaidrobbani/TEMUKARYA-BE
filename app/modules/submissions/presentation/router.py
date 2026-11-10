from fastapi import APIRouter, Body, Depends, File, Form, UploadFile, status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.core.responses import ApiResponse, error_responses, success_response
from app.modules.submissions.application.use_cases import (
    ApproveSubmission,
    GetSubmission,
    ListSubmissions,
    OpenSubmissionFile,
    RequestRevision,
    RevisionRequestInput,
    SubmitResult,
    SubmitResultInput,
    UploadedFile,
)
from app.modules.submissions.domain.entities import RevisionItem
from app.modules.submissions.presentation.dependencies import (
    approve_submission_use_case,
    get_submission_use_case,
    list_submissions_use_case,
    open_submission_file_use_case,
    request_revision_use_case,
    submit_result_use_case,
)
from app.modules.submissions.presentation.schemas import (
    ApproveSubmissionRequest,
    CompletionResponse,
    RevisionRequest,
    SubmissionListResponse,
    SubmissionResponse,
)
from app.modules.workflow.application.dto import Actor
from app.modules.workflow.presentation.providers import get_actor

router = APIRouter(tags=["submissions"])


def _size(upload: UploadFile) -> int:
    if upload.size is not None:
        return upload.size
    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)
    return size


@router.post(
    "/projects/{project_id}/submissions",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[SubmissionResponse],
    responses=error_responses(400, 401, 403, 404, 409, 413, 415, 422),
    summary="Freelancer mengirim hasil / hasil revisi (multipart)",
)
def submit_result(
    project_id: str,
    files: list[UploadFile] = File(default=[], description="Maks. 10 file, masing-masing 50 MB"),
    note: str | None = Form(None, description="Catatan & panduan review untuk UMKM"),
    result_url: str | None = Form(None, description="Tautan hasil (mis. Google Drive)"),
    actor: Actor = Depends(get_actor),
    use_case: SubmitResult = Depends(submit_result_use_case),
):
    uploads = tuple(UploadedFile(f.filename or "", _size(f), f.file) for f in files)
    submission = use_case.execute(actor, project_id, SubmitResultInput(note, result_url, uploads))
    return success_response("Hasil kerja dikirim ke UMKM", SubmissionResponse.build(submission))


@router.get(
    "/projects/{project_id}/submissions",
    response_model=ApiResponse[SubmissionListResponse],
    responses=error_responses(401, 404),
    summary="Semua versi kiriman hasil beserta review-nya",
)
def list_submissions(
    project_id: str,
    actor: Actor = Depends(get_actor),
    use_case: ListSubmissions = Depends(list_submissions_use_case),
):
    return success_response("Daftar kiriman hasil", SubmissionListResponse.build(use_case.execute(actor, project_id)))


@router.get(
    "/projects/{project_id}/submissions/{submission_id}",
    response_model=ApiResponse[SubmissionResponse],
    responses=error_responses(401, 404),
)
def get_submission(
    project_id: str,
    submission_id: str,
    actor: Actor = Depends(get_actor),
    use_case: GetSubmission = Depends(get_submission_use_case),
):
    submission = use_case.execute(actor, project_id, submission_id)
    return success_response("Detail kiriman hasil", SubmissionResponse.build(submission))


@router.get(
    "/projects/{project_id}/submissions/{submission_id}/files/{file_id}",
    responses={200: {"content": {"application/octet-stream": {}}}, **error_responses(401, 404, 503)},
    summary="Unduh file hasil (biner)",
)
def download_submission_file(
    project_id: str,
    submission_id: str,
    file_id: str,
    actor: Actor = Depends(get_actor),
    use_case: OpenSubmissionFile = Depends(open_submission_file_use_case),
):
    file, stream = use_case.execute(actor, project_id, submission_id, file_id)

    def chunks():
        while chunk := stream.read(64 * 1024):
            yield chunk

    extension = file.storage_key.rsplit(".", 1)[-1]
    return StreamingResponse(
        chunks(),
        media_type=file.mime_type,
        headers={
            "Content-Length": str(file.file_size_bytes),
            # Nama file client tidak dimasukkan ke header; nama asli ada di metadata JSON.
            "Content-Disposition": f'attachment; filename="hasil-{file.id[:8]}.{extension}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
        background=BackgroundTask(stream.close),
    )


@router.post(
    "/projects/{project_id}/submissions/{submission_id}/request-revision",
    response_model=ApiResponse[SubmissionResponse],
    responses=error_responses(400, 401, 403, 404, 409, 422),
    summary="UMKM meminta revisi kiriman terbaru",
)
def request_revision(
    project_id: str,
    submission_id: str,
    body: RevisionRequest,
    actor: Actor = Depends(get_actor),
    use_case: RequestRevision = Depends(request_revision_use_case),
):
    data = RevisionRequestInput(
        note=body.note,
        focus_areas=tuple(body.focus_areas),
        items=tuple(RevisionItem(i.title, i.detail, i.area) for i in body.items),
    )
    submission = use_case.execute(actor, project_id, submission_id, data)
    return success_response("Permintaan revisi dikirim ke freelancer", SubmissionResponse.build(submission))


@router.post(
    "/projects/{project_id}/submissions/{submission_id}/approve",
    response_model=ApiResponse[CompletionResponse],
    responses=error_responses(400, 401, 403, 404, 409, 422),
    summary="UMKM menyetujui hasil: project selesai dan dana diteruskan",
)
def approve_submission(
    project_id: str,
    submission_id: str,
    body: ApproveSubmissionRequest | None = Body(None),
    actor: Actor = Depends(get_actor),
    use_case: ApproveSubmission = Depends(approve_submission_use_case),
):
    review = body.review.to_input() if body and body.review else None
    result = use_case.execute(actor, project_id, submission_id, review)
    message = "Proyek sudah selesai sebelumnya" if result.already_completed else "Proyek selesai, dana diteruskan ke freelancer"
    return success_response(message, CompletionResponse.build(result))
