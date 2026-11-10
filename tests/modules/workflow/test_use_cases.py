from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.modules.workflow.domain.entities import Party, WorkflowAction
from tests.modules.workflow.fakes import FREELANCER_ID, NOW, OTHER_FREELANCER_ID, PROJECT_ID, UMKM_ID
from tests.modules.workflow.world import FREELANCER, OTHER_FREELANCER, OTHER_UMKM, UMKM, World

APP_ID = f"app-{FREELANCER_ID}-{PROJECT_ID}"


@pytest.fixture
def w():
    return World()


def statuses(w):
    return [h.new_status for h in w.store.history]


class TestSelectFreelancer:
    def test_from_application_fills_agreement_and_closes_others(self, w):
        w.store.add_application(price=1_400_000, days=14)
        w.store.add_application(OTHER_FREELANCER_ID)

        detail = w.select(application_id=APP_ID)

        assert detail.project.status == "MENUNGGU_KESEPAKATAN"
        agreement = detail.agreement
        assert agreement.freelancer_id == FREELANCER_ID
        assert agreement.selection_source == "APPLICATION"
        assert agreement.agreed_price == 1_400_000
        assert agreement.agreed_deadline == date(2026, 11, 24)
        assert agreement.duration_days == 14
        assert agreement.scope_of_work == "Desain logo dan kemasan pouch 250gr"
        assert w.store.applications[APP_ID].status == "ACCEPTED"
        assert w.store.applications[f"app-{OTHER_FREELANCER_ID}-{PROJECT_ID}"].status == "NOT_SELECTED"
        assert statuses(w) == ["MENUNGGU_KESEPAKATAN"]
        assert w.store.history[0].action == "SELECT_FREELANCER"
        assert [n.notification_type for n in w.store.notifications_for(FREELANCER_ID)] == ["APPLICATION_ACCEPTED"]
        assert "Kedai Kopi Senja" in w.store.notifications_for(FREELANCER_ID)[0].body
        assert [n.notification_type for n in w.store.notifications_for(OTHER_FREELANCER_ID)] == [
            "APPLICATION_NOT_SELECTED"
        ]
        assert w.uow.commits == 1
        assert PROJECT_ID in w.store.locks

    def test_direct_from_profile_uses_budget_and_deadline(self, w):
        detail = w.select(freelancer_id=FREELANCER_ID, scope_of_work="  2 alternatif logo + mockup pouch ")

        assert detail.agreement.selection_source == "DIRECT"
        assert detail.agreement.application_id is None
        assert detail.agreement.agreed_price == 1_500_000
        assert detail.agreement.agreed_deadline == date(2026, 12, 1)
        assert detail.agreement.scope_of_work == "2 alternatif logo + mockup pouch"

    def test_direct_selection_links_existing_application(self, w):
        w.store.add_application(price=1_200_000)

        detail = w.select(freelancer_id=FREELANCER_ID)

        assert detail.agreement.selection_source == "APPLICATION"
        assert detail.agreement.application_id == APP_ID
        assert detail.agreement.agreed_price == 1_200_000

    def test_both_or_none_ids_rejected(self, w):
        with pytest.raises(BadRequestError):
            w.select()
        with pytest.raises(BadRequestError):
            w.select(application_id=APP_ID, freelancer_id=FREELANCER_ID)

    def test_only_umkm_role(self, w):
        with pytest.raises(ForbiddenError):
            w.select(FREELANCER, freelancer_id=FREELANCER_ID)

    def test_not_owner_gets_404(self, w):
        with pytest.raises(NotFoundError, match="Proyek tidak ditemukan"):
            w.select(OTHER_UMKM, freelancer_id=FREELANCER_ID)

    def test_unknown_project(self, w):
        with pytest.raises(NotFoundError):
            w.select(project_id="nope", freelancer_id=FREELANCER_ID)

    def test_application_of_other_project_rejected(self, w):
        w.store.add_project("project-2")
        w.store.add_application(project_id="project-2")
        with pytest.raises(NotFoundError, match="Pengajuan tidak ditemukan"):
            w.select(application_id=f"app-{FREELANCER_ID}-project-2")

    def test_inactive_application_rejected(self, w):
        w.store.add_application()
        w.workflow.set_application_status(APP_ID, "CANCELLED")
        with pytest.raises(ConflictError, match="tidak aktif"):
            w.select(application_id=APP_ID)

    def test_unknown_freelancer(self, w):
        with pytest.raises(NotFoundError, match="Freelancer tidak ditemukan"):
            w.select(freelancer_id=UMKM_ID)

    def test_second_selection_rejected(self, w):
        w.to_negotiation()
        with pytest.raises(ConflictError, match="sudah memiliki freelancer"):
            w.select(freelancer_id=OTHER_FREELANCER_ID)
        assert len(w.store.agreements) == 1

    def test_cancelled_project_rejected(self, w):
        w.cancel()
        with pytest.raises(ConflictError, match="Terbuka"):
            w.select(freelancer_id=FREELANCER_ID)

    def test_unpublished_project_rejected(self, w):
        w.store.add_project(published_at=None)
        with pytest.raises(ConflictError, match="dipublikasikan"):
            w.select(freelancer_id=FREELANCER_ID)

    def test_direct_with_past_deadline_rejected(self, w):
        w.store.add_project(deadline=date(2026, 11, 10))
        with pytest.raises(BadRequestError, match="Deadline"):
            w.select(freelancer_id=FREELANCER_ID)

    def test_scope_too_long(self, w):
        with pytest.raises(BadRequestError):
            w.select(freelancer_id=FREELANCER_ID, scope_of_work="x" * 5001)
        assert w.store.agreements == {}


class TestAgreementAccess:
    def test_selected_freelancer_can_read(self, w):
        w.to_negotiation()
        detail = w.get_agreement(FREELANCER)
        assert detail.my_party == Party.FREELANCER
        assert detail.parties.umkm.subtitle == "Kedai Kopi Senja"
        assert detail.parties.freelancer.name == "Andi Ramadhan"

    def test_other_freelancer_gets_404(self, w):
        w.to_negotiation()
        with pytest.raises(NotFoundError):
            w.get_agreement(OTHER_FREELANCER)

    def test_no_agreement_yet(self, w):
        with pytest.raises(NotFoundError, match="Kesepakatan belum dibuat"):
            w.get_agreement(UMKM)

    def test_freelancer_cannot_see_open_project_workflow(self, w):
        with pytest.raises(NotFoundError):
            w.detail(FREELANCER)


class TestUpdateAgreement:
    def test_change_resets_both_approvals_and_bumps_version(self, w):
        w.to_negotiation()
        w.set_plan()
        w.approve(FREELANCER)

        detail = w.update_agreement(UMKM, agreed_price=1_600_000, scope_of_work="3 alternatif logo")

        assert detail.agreement.agreed_price == 1_600_000
        assert detail.agreement.agreement_version == 2
        assert detail.agreement.freelancer_approved_at is None
        assert detail.agreement.umkm_approved_at is None
        assert w.store.notifications_for(FREELANCER_ID)[-1].notification_type == "AGREEMENT_UPDATED"

    def test_duration_days_sets_deadline_from_agreement_date(self, w):
        w.to_negotiation()
        detail = w.update_agreement(FREELANCER, duration_days=20)
        assert detail.agreement.agreed_deadline == date(2026, 11, 30)
        assert detail.agreement.duration_days == 20
        assert w.store.notifications_for(UMKM_ID)[-1].notification_type == "AGREEMENT_UPDATED"

    def test_same_values_is_noop(self, w):
        w.to_negotiation()
        commits = w.uow.commits
        detail = w.update_agreement(UMKM, agreed_price=1_500_000)
        assert detail.agreement.agreement_version == 1
        assert w.uow.commits == commits

    @pytest.mark.parametrize(
        "data, message",
        [
            ({}, "Tidak ada perubahan"),
            ({"agreed_deadline": date(2026, 12, 1), "duration_days": 3}, "salah satu"),
            ({"agreed_price": 0}, "Nilai proyek"),
            ({"scope_of_work": "   "}, "wajib diisi"),
            ({"duration_days": 0}, "Durasi"),
            ({"duration_days": 366}, "Durasi"),
            ({"agreed_deadline": date(2026, 11, 10)}, "setelah hari ini"),
            ({"agreed_deadline": date(2028, 1, 1)}, "maksimal"),
        ],
    )
    def test_invalid_input(self, w, data, message):
        w.to_negotiation()
        with pytest.raises(BadRequestError, match=message):
            w.update_agreement(UMKM, **data)

    def test_locked_after_final(self, w):
        w.to_waiting_payment()
        with pytest.raises(ConflictError, match="sudah final"):
            w.update_agreement(UMKM, agreed_price=2_000_000)

    def test_outsider_rejected(self, w):
        w.to_negotiation()
        with pytest.raises(NotFoundError):
            w.update_agreement(OTHER_FREELANCER, agreed_price=2_000_000)


class TestApproveAgreement:
    def test_requires_complete_milestone_plan(self, w):
        w.to_negotiation()
        w.set_plan(("40",))
        with pytest.raises(ConflictError) as error:
            w.approve(FREELANCER)
        assert error.value.code == "MILESTONE_PLAN_INCOMPLETE"
        assert "40%" in error.value.message

    def test_one_side_keeps_waiting_and_notifies_other(self, w):
        w.to_negotiation()
        w.set_plan()

        detail = w.approve(FREELANCER)

        assert detail.project.status == "MENUNGGU_KESEPAKATAN"
        assert detail.agreement.freelancer_approved_at == NOW
        assert WorkflowAction.APPROVE_AGREEMENT not in w.detail(FREELANCER).available_actions
        assert WorkflowAction.APPROVE_AGREEMENT in w.detail(UMKM).available_actions
        assert w.store.notifications_for(UMKM_ID)[-1].notification_type == "AGREEMENT_APPROVED"
        assert w.store.payments == {}

    def test_both_sides_finalize_and_create_invoice(self, w):
        w.to_negotiation()
        w.set_plan()
        w.approve(FREELANCER)

        detail = w.approve(UMKM)

        assert detail.project.status == "MENUNGGU_PEMBAYARAN"
        assert detail.agreement.status == "APPROVED"
        payment = w.store.payment_for()
        assert (payment.gross_amount, payment.platform_fee_amount, payment.freelancer_amount) == (
            1_500_000,
            75_000,
            1_425_000,
        )
        assert payment.status == "MENUNGGU"
        assert payment.expires_at == NOW + timedelta(minutes=15)
        assert statuses(w)[-1] == "MENUNGGU_PEMBAYARAN"
        finalized = [n for n in w.store.notifications if n.notification_type == "AGREEMENT_FINALIZED"]
        assert {n.user_id for n in finalized} == {UMKM_ID, FREELANCER_ID}

    def test_repeat_click_is_idempotent(self, w):
        w.to_negotiation()
        w.set_plan()
        w.approve(FREELANCER)
        notifications = len(w.store.notifications)

        w.approve(FREELANCER)

        assert len(w.store.notifications) == notifications

    def test_repeat_after_final_is_idempotent(self, w):
        w.to_waiting_payment()
        detail = w.approve(UMKM)
        assert detail.project.status == "MENUNGGU_PEMBAYARAN"
        assert len(w.store.payments) == 1

    def test_stale_version_rejected(self, w):
        w.to_negotiation()
        w.set_plan()
        w.update_agreement(FREELANCER, agreed_price=1_700_000)
        with pytest.raises(ConflictError) as error:
            w.approve(UMKM, version=1)
        assert error.value.code == "AGREEMENT_CHANGED"
        assert w.approve(UMKM, version=2).agreement.umkm_approved_at is not None

    def test_cancelled_project(self, w):
        w.to_negotiation()
        w.cancel()
        with pytest.raises(ConflictError, match="dibatalkan"):
            w.approve(UMKM)

    def test_without_agreement(self, w):
        with pytest.raises(NotFoundError):
            w.approve(UMKM)


class TestRequestChanges:
    def test_umkm_requests_changes(self, w):
        w.to_negotiation()
        w.set_plan()
        w.approve(FREELANCER)

        detail = w.request_changes(note=" Pisahkan revisi logo ")

        assert detail.agreement.freelancer_approved_at is None
        assert detail.agreement.change_request_note == "Pisahkan revisi logo"
        assert detail.agreement.change_requested_at == NOW
        last = w.store.notifications_for(FREELANCER_ID)[-1]
        assert last.notification_type == "AGREEMENT_CHANGES_REQUESTED"
        assert last.body == "Pisahkan revisi logo"

    def test_freelancer_cannot(self, w):
        w.to_negotiation()
        with pytest.raises(ForbiddenError):
            w.request_changes(FREELANCER)

    @pytest.mark.parametrize("note", ["", "   ", "x" * 2001])
    def test_note_required(self, w, note):
        w.to_negotiation()
        with pytest.raises(BadRequestError):
            w.request_changes(note=note)

    def test_after_final_rejected(self, w):
        w.to_waiting_payment()
        with pytest.raises(ConflictError):
            w.request_changes()


class TestCancelProject:
    def test_umkm_cancels_open_project_and_applicants_notified(self, w):
        w.store.add_application()

        detail = w.cancel(UMKM, "KEBUTUHAN_BERUBAH")

        assert detail.project.status == "DIBATALKAN"
        assert w.store.applications[APP_ID].status == "CANCELLED"
        assert detail.cancellation.reason == "KEBUTUHAN_BERUBAH"
        assert detail.cancellation.cancelled_by == Party.UMKM
        assert w.store.notifications_for(FREELANCER_ID)[-1].notification_type == "PROJECT_CANCELLED"
        assert detail.available_actions == []

    def test_freelancer_cannot_cancel_open_project(self, w):
        with pytest.raises(NotFoundError):
            w.cancel(FREELANCER)

    def test_freelancer_cancels_during_negotiation(self, w):
        w.to_negotiation()

        detail = w.cancel(FREELANCER, "LAINNYA", "Jadwal bentrok proyek lain")

        assert detail.project.status == "DIBATALKAN"
        assert detail.agreement.status == "CANCELLED"
        assert detail.cancellation.cancelled_by == Party.FREELANCER
        assert detail.cancellation.note == "Jadwal bentrok proyek lain"
        assert w.store.applications[APP_ID].status == "CANCELLED"
        notification = w.store.notifications_for(UMKM_ID)[-1]
        assert notification.notification_type == "PROJECT_CANCELLED"
        assert "Alasan lainnya" in notification.body
        assert w.store.history[-1].reason_code == "LAINNYA"

    def test_cancel_while_waiting_payment_cancels_invoice(self, w):
        w.to_waiting_payment()

        w.cancel(UMKM)

        assert w.store.payment_for().status == "DIBATALKAN"
        assert w.store.payment_for().expires_at is None

    def test_cannot_cancel_after_payment(self, w):
        w.to_ready()
        with pytest.raises(ConflictError, match="setelah pembayaran"):
            w.cancel(UMKM)
        with pytest.raises(ConflictError):
            w.cancel(FREELANCER)

    def test_cannot_cancel_twice(self, w):
        w.cancel()
        with pytest.raises(ConflictError, match="sudah dibatalkan"):
            w.cancel()

    @pytest.mark.parametrize(
        "reason, note, message",
        [
            ("ASAL", None, "tidak valid"),
            ("LAINNYA", None, "Tuliskan"),
            ("LAINNYA", "   ", "Tuliskan"),
            ("HARGA_TIDAK_SESUAI", "x" * 501, "maksimal"),
        ],
    )
    def test_invalid_reason(self, w, reason, note, message):
        with pytest.raises(BadRequestError, match=message):
            w.cancel(UMKM, reason, note)
        assert w.project.status == "TERBUKA"


class TestStartWork:
    def test_freelancer_starts_after_payment(self, w):
        w.to_ready()
        w.clock.advance(hours=1)

        detail = w.start()

        assert detail.project.status == "SEDANG_DIKERJAKAN"
        assert detail.project.started_at == w.clock.now
        assert w.store.notifications_for(UMKM_ID)[-1].notification_type == "WORK_STARTED"

    def test_unpaid_project_rejected_with_reason(self, w):
        w.to_waiting_payment()
        with pytest.raises(ConflictError, match="belum dibayar"):
            w.start()
        assert w.project.status == "MENUNGGU_PEMBAYARAN"

    def test_negotiation_rejected(self, w):
        w.to_negotiation()
        with pytest.raises(ConflictError, match="Kesepakatan belum disetujui"):
            w.start()

    def test_umkm_cannot_start(self, w):
        w.to_ready()
        with pytest.raises(ForbiddenError):
            w.start(UMKM)

    def test_other_freelancer_gets_404(self, w):
        w.to_ready()
        with pytest.raises(NotFoundError):
            w.start(OTHER_FREELANCER)

    def test_repeat_start_is_idempotent(self, w):
        w.to_working()
        started_at = w.project.started_at
        history = len(w.store.history)
        w.clock.advance(hours=2)

        w.start()

        assert w.project.started_at == started_at
        assert len(w.store.history) == history

    def test_after_submission_rejected(self, w):
        w.to_review()
        with pytest.raises(ConflictError, match="sudah dimulai"):
            w.start()


class TestWorkflowDetail:
    def test_available_actions_per_status(self, w):
        assert w.detail(UMKM).available_actions == [WorkflowAction.SELECT_FREELANCER, WorkflowAction.CANCEL_PROJECT]
        w.to_negotiation()
        assert w.detail(FREELANCER).available_actions == [
            WorkflowAction.UPDATE_AGREEMENT,
            WorkflowAction.EDIT_MILESTONE_PLAN,
            WorkflowAction.APPROVE_AGREEMENT,
            WorkflowAction.CANCEL_PROJECT,
        ]
        assert WorkflowAction.REQUEST_AGREEMENT_CHANGES in w.detail(UMKM).available_actions
        w.set_plan()
        w.approve(FREELANCER)
        w.approve(UMKM)
        assert w.detail(UMKM).available_actions == [WorkflowAction.PAY, WorkflowAction.CANCEL_PROJECT]
        assert w.detail(FREELANCER).available_actions == [WorkflowAction.CANCEL_PROJECT]
        w.pay()
        assert w.detail(UMKM).available_actions == []
        assert w.detail(FREELANCER).available_actions == [WorkflowAction.START_WORK]
        w.start()
        assert w.detail(FREELANCER).available_actions == [
            WorkflowAction.COMPLETE_MILESTONE,
            WorkflowAction.SUBMIT_RESULT,
        ]
        submission = w.submit(url="https://drive.google.com/x")
        assert w.detail(UMKM).available_actions == [WorkflowAction.REQUEST_REVISION, WorkflowAction.APPROVE_RESULT]
        assert w.detail(FREELANCER).available_actions == []
        w.approve_submission(submission.id)
        assert w.detail(UMKM).available_actions == [WorkflowAction.GIVE_REVIEW]
        w.create_review(rating=5)
        assert w.detail(UMKM).available_actions == []
        assert w.detail(UMKM).has_review is True

    def test_full_history_is_recorded_in_order(self, w):
        w.to_completed()
        assert statuses(w) == [
            "MENUNGGU_KESEPAKATAN",
            "MENUNGGU_PEMBAYARAN",
            "SIAP_DIKERJAKAN",
            "SEDANG_DIKERJAKAN",
            "MENUNGGU_REVIEW",
            "SELESAI",
        ]
        assert [h.change_source for h in w.store.history].count("SYSTEM") == 1
        detail = w.detail(FREELANCER)
        assert detail.payment.fund_status == "RELEASED"
        assert detail.latest_submission.decision == "APPROVED"


class TestListMyProjects:
    def test_umkm_sees_all_own_projects_with_counts(self, w):
        w.store.add_project("project-2", title="Foto Menu")
        w.store.add_application(project_id="project-2")
        w.store.add_project("project-x", umkm_id="umkm-2")
        w.to_negotiation()
        w.set_plan()

        page = w.my_projects(UMKM)

        assert {r.project.id for r in page.items} == {PROJECT_ID, "project-2"}
        assert page.status_counts == {"MENUNGGU_KESEPAKATAN": 1, "TERBUKA": 1}
        row = next(r for r in page.items if r.project.id == PROJECT_ID)
        assert row.counterpart.name == "Andi Ramadhan"
        assert row.progress_percent == 0.0
        assert next(r for r in page.items if r.project.id == "project-2").application_count == 1

    def test_freelancer_sees_only_selected_projects(self, w):
        w.to_working()
        w.store.milestones[PROJECT_ID] = [(Decimal("20"), True), (Decimal("80"), False)]
        w.store.add_project("project-2")

        page = w.my_projects(FREELANCER)

        assert [r.project.id for r in page.items] == [PROJECT_ID]
        assert page.items[0].counterpart.subtitle == "Kedai Kopi Senja"
        assert page.items[0].progress_percent == 20.0
        assert page.items[0].payment.fund_status == "HELD"

    def test_status_filter_and_paging(self, w):
        w.store.add_project("project-2")
        page = w.my_projects(UMKM, status="TERBUKA", limit=1)
        assert len(page.items) == 1
        assert page.has_more is True
        assert w.my_projects(UMKM, status="SELESAI").items == []

    @pytest.mark.parametrize(
        "kwargs, error",
        [
            ({"status": "ASAL"}, BadRequestError),
            ({"limit": 0}, BadRequestError),
            ({"limit": 101}, BadRequestError),
            ({"offset": -1}, BadRequestError),
        ],
    )
    def test_invalid_query(self, w, kwargs, error):
        with pytest.raises(error):
            w.my_projects(UMKM, **kwargs)

    def test_admin_rejected(self, w):
        from tests.modules.workflow.world import ADMIN

        with pytest.raises(ForbiddenError):
            w.my_projects(ADMIN)


class TestApprovalResetter:
    def test_reset_clears_approvals_and_bumps_version(self, w):
        from app.modules.workflow.application.services import ApprovalResetter

        w.to_negotiation()
        w.set_plan()
        w.approve(FREELANCER)

        updated = ApprovalResetter(w.workflow, w.clock).reset(PROJECT_ID)

        assert updated.agreement_version == 2
        assert updated.freelancer_approved_at is None
        assert w.store.agreement_for().agreement_version == 2
        assert PROJECT_ID in w.store.locks

    @pytest.mark.parametrize("setup", [None, "to_waiting_payment"])
    def test_reset_rejected_without_pending_agreement(self, w, setup):
        from app.modules.workflow.application.services import ApprovalResetter

        if setup:
            getattr(w, setup)()
        with pytest.raises(ConflictError):
            ApprovalResetter(w.workflow, w.clock).reset(PROJECT_ID)
