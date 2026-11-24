from fastapi import APIRouter, Body, Depends, Query, status

from app.core.responses import ApiResponse, error_responses, success_response
from app.modules.workflow.application.dto import (
    Actor,
    CancelProjectInput,
    SelectFreelancerInput,
    UpdateAgreementInput,
)
from app.modules.workflow.application.use_cases import (
    ApproveAgreement,
    CancelProject,
    GetAgreement,
    GetProjectWorkflow,
    ListMyProjects,
    RequestAgreementChanges,
    SelectFreelancer,
    StartWork,
    UpdateAgreement,
)
from app.modules.workflow.domain.entities import AgreementStatus, ProjectStatus
from app.modules.workflow.presentation.dependencies import (
    approve_agreement_use_case,
    cancel_project_use_case,
    get_actor,
    get_agreement_use_case,
    get_project_workflow_use_case,
    list_my_projects_use_case,
    request_changes_use_case,
    select_freelancer_use_case,
    start_work_use_case,
    update_agreement_use_case,
)
from app.modules.workflow.presentation.schemas import (
    ApproveAgreementRequest,
    CancelProjectRequest,
    MyProjectsResponse,
    RequestChangesRequest,
    SelectFreelancerRequest,
    UpdateAgreementRequest,
    WorkflowDetailResponse,
)

router = APIRouter(tags=["workflow"])

Detail = ApiResponse[WorkflowDetailResponse]


@router.get(
    "/workflow/projects",
    response_model=ApiResponse[MyProjectsResponse],
    responses=error_responses(400, 401, 403, 422),
    summary="Project Saya (UMKM) / Project Aktif (freelancer)",
)
def list_my_projects(
    status_filter: ProjectStatus | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor: Actor = Depends(get_actor),
    use_case: ListMyProjects = Depends(list_my_projects_use_case),
):
    page = use_case.execute(actor, status_filter.value if status_filter else None, limit, offset)
    return success_response("Daftar proyek", MyProjectsResponse.build(page, limit, offset))


@router.get(
    "/projects/{project_id}/workflow",
    response_model=Detail,
    responses=error_responses(401, 404),
    summary="Detail tracking project: status, kesepakatan, pembayaran, riwayat, tombol yang tersedia",
)
def get_project_workflow(
    project_id: str,
    actor: Actor = Depends(get_actor),
    use_case: GetProjectWorkflow = Depends(get_project_workflow_use_case),
):
    return success_response("Detail alur proyek", WorkflowDetailResponse.build(use_case.execute(actor, project_id)))


@router.post(
    "/projects/{project_id}/agreement",
    status_code=status.HTTP_201_CREATED,
    response_model=Detail,
    responses=error_responses(400, 401, 403, 404, 409, 422),
    summary="UMKM memilih freelancer (Setujui & Buat / Pilih & Buat Kesepakatan)",
)
def select_freelancer(
    project_id: str,
    body: SelectFreelancerRequest,
    actor: Actor = Depends(get_actor),
    use_case: SelectFreelancer = Depends(select_freelancer_use_case),
):
    detail = use_case.execute(actor, project_id, SelectFreelancerInput(**body.model_dump()))
    return success_response("Freelancer dipilih, lanjutkan negosiasi kesepakatan", WorkflowDetailResponse.build(detail))


@router.get(
    "/projects/{project_id}/agreement",
    response_model=Detail,
    responses=error_responses(401, 404),
)
def get_agreement(
    project_id: str,
    actor: Actor = Depends(get_actor),
    use_case: GetAgreement = Depends(get_agreement_use_case),
):
    return success_response("Detail kesepakatan", WorkflowDetailResponse.build(use_case.execute(actor, project_id)))


@router.patch(
    "/projects/{project_id}/agreement",
    response_model=Detail,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Ubah detail kesepakatan (membatalkan persetujuan kedua pihak)",
)
def update_agreement(
    project_id: str,
    body: UpdateAgreementRequest,
    actor: Actor = Depends(get_actor),
    use_case: UpdateAgreement = Depends(update_agreement_use_case),
):
    data = UpdateAgreementInput(**body.model_dump())
    return success_response(
        "Kesepakatan diperbarui", WorkflowDetailResponse.build(use_case.execute(actor, project_id, data))
    )


@router.post(
    "/projects/{project_id}/agreement/approve",
    response_model=Detail,
    responses=error_responses(401, 404, 409, 422),
    summary="Lanjut Project / Setujui Rencana / Ajukan ke UMKM",
)
def approve_agreement(
    project_id: str,
    body: ApproveAgreementRequest | None = Body(None),
    actor: Actor = Depends(get_actor),
    use_case: ApproveAgreement = Depends(approve_agreement_use_case),
):
    detail = use_case.execute(actor, project_id, body.agreement_version if body else None)
    if detail.agreement.status == AgreementStatus.APPROVED:
        message = "Kesepakatan final, proyek menunggu pembayaran"
    else:
        message = "Persetujuan tercatat, menunggu pihak lain"
    return success_response(message, WorkflowDetailResponse.build(detail))


@router.post(
    "/projects/{project_id}/agreement/request-changes",
    response_model=Detail,
    responses=error_responses(400, 401, 403, 404, 409, 422),
    summary="UMKM meminta freelancer mengubah rencana (Minta Ubah)",
)
def request_agreement_changes(
    project_id: str,
    body: RequestChangesRequest,
    actor: Actor = Depends(get_actor),
    use_case: RequestAgreementChanges = Depends(request_changes_use_case),
):
    detail = use_case.execute(actor, project_id, body.note)
    return success_response("Permintaan perubahan dikirim ke freelancer", WorkflowDetailResponse.build(detail))


@router.post(
    "/projects/{project_id}/cancel",
    response_model=Detail,
    responses=error_responses(400, 401, 404, 409, 422),
    summary="Batalkan project (sebelum pembayaran berhasil)",
)
def cancel_project(
    project_id: str,
    body: CancelProjectRequest,
    actor: Actor = Depends(get_actor),
    use_case: CancelProject = Depends(cancel_project_use_case),
):
    detail = use_case.execute(actor, project_id, CancelProjectInput(reason=body.reason.value, note=body.note))
    return success_response("Project dibatalkan", WorkflowDetailResponse.build(detail))


@router.post(
    "/projects/{project_id}/start",
    response_model=Detail,
    responses=error_responses(401, 403, 404, 409),
    summary="Freelancer memulai pengerjaan",
)
def start_work(
    project_id: str,
    actor: Actor = Depends(get_actor),
    use_case: StartWork = Depends(start_work_use_case),
):
    detail = use_case.execute(actor, project_id)
    return success_response("Pengerjaan dimulai", WorkflowDetailResponse.build(detail))
