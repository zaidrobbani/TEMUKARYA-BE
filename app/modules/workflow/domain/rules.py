from app.modules.workflow.domain.entities import (
    Agreement,
    Party,
    ProjectStatus,
    WorkflowAction,
    status_label,
)

# Pembatalan hanya sebelum pembayaran berhasil (PRD Fungsi 2).
CANCELLABLE_STATUSES = {
    ProjectStatus.TERBUKA,
    ProjectStatus.MENUNGGU_KESEPAKATAN,
    ProjectStatus.MENUNGGU_PEMBAYARAN,
}
WORKING_STATUSES = {ProjectStatus.SEDANG_DIKERJAKAN, ProjectStatus.REVISI}

# Alasan penolakan per status, supaya pesan error menjelaskan tahap yang sedang berjalan.
_START_BLOCKERS = {
    ProjectStatus.TERBUKA: "Proyek belum memiliki freelancer terpilih",
    ProjectStatus.MENUNGGU_KESEPAKATAN: "Kesepakatan belum disetujui kedua pihak",
    ProjectStatus.MENUNGGU_PEMBAYARAN: "Proyek belum dibayar, tunggu pembayaran UMKM berhasil",
    ProjectStatus.DIBATALKAN: "Proyek sudah dibatalkan",
}


def start_blocker(status: str) -> str:
    return _START_BLOCKERS.get(ProjectStatus(status), f"Pengerjaan sudah dimulai (status {status_label(status)})")


def cancel_blocker(status: str, party: Party) -> str | None:
    """None berarti boleh membatalkan."""
    project_status = ProjectStatus(status)
    if project_status == ProjectStatus.DIBATALKAN:
        return "Proyek sudah dibatalkan"
    if project_status not in CANCELLABLE_STATUSES:
        return "Proyek tidak dapat dibatalkan setelah pembayaran berhasil"
    if project_status == ProjectStatus.TERBUKA and party != Party.UMKM:
        return "Hanya UMKM pemilik yang dapat membatalkan proyek terbuka"
    return None


def available_actions(
    status: str,
    party: Party,
    agreement: Agreement | None,
    has_review: bool,
) -> list[WorkflowAction]:
    project_status = ProjectStatus(status)
    actions: list[WorkflowAction] = []
    is_umkm = party == Party.UMKM

    if project_status == ProjectStatus.TERBUKA and is_umkm:
        actions.append(WorkflowAction.SELECT_FREELANCER)
    elif project_status == ProjectStatus.MENUNGGU_KESEPAKATAN:
        actions += [WorkflowAction.UPDATE_AGREEMENT, WorkflowAction.EDIT_MILESTONE_PLAN]
        if agreement is not None and agreement.approved_at(party) is None:
            actions.append(WorkflowAction.APPROVE_AGREEMENT)
        if is_umkm:
            actions.append(WorkflowAction.REQUEST_AGREEMENT_CHANGES)
    elif project_status == ProjectStatus.MENUNGGU_PEMBAYARAN and is_umkm:
        actions.append(WorkflowAction.PAY)
    elif project_status == ProjectStatus.SIAP_DIKERJAKAN and not is_umkm:
        actions.append(WorkflowAction.START_WORK)
    elif project_status in WORKING_STATUSES and not is_umkm:
        actions += [WorkflowAction.COMPLETE_MILESTONE, WorkflowAction.SUBMIT_RESULT]
    elif project_status == ProjectStatus.MENUNGGU_REVIEW and is_umkm:
        actions += [WorkflowAction.REQUEST_REVISION, WorkflowAction.APPROVE_RESULT]
    elif project_status == ProjectStatus.SELESAI and is_umkm and not has_review:
        actions.append(WorkflowAction.GIVE_REVIEW)

    if cancel_blocker(status, party) is None:
        actions.append(WorkflowAction.CANCEL_PROJECT)
    return actions



ALLOWED_TRANSITIONS: dict[ProjectStatus, set[ProjectStatus]] = {
    ProjectStatus.TERBUKA: {ProjectStatus.MENUNGGU_KESEPAKATAN, ProjectStatus.DIBATALKAN},
    ProjectStatus.MENUNGGU_KESEPAKATAN: {ProjectStatus.MENUNGGU_PEMBAYARAN, ProjectStatus.DIBATALKAN},
    ProjectStatus.MENUNGGU_PEMBAYARAN: {ProjectStatus.SIAP_DIKERJAKAN, ProjectStatus.DIBATALKAN},
    ProjectStatus.SIAP_DIKERJAKAN: {ProjectStatus.SEDANG_DIKERJAKAN},
    ProjectStatus.SEDANG_DIKERJAKAN: {ProjectStatus.MENUNGGU_REVIEW},
    ProjectStatus.MENUNGGU_REVIEW: {ProjectStatus.REVISI, ProjectStatus.SELESAI},
    ProjectStatus.REVISI: {ProjectStatus.MENUNGGU_REVIEW},
    ProjectStatus.SELESAI: set(),
    ProjectStatus.DIBATALKAN: set(),
}


def can_transition(current: str, new: str) -> bool:
    return ProjectStatus(new) in ALLOWED_TRANSITIONS[ProjectStatus(current)]
