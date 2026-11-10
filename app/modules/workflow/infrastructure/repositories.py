from datetime import datetime
from decimal import Decimal

from sqlalchemy import exists, select, text, update
from sqlalchemy.orm import Session

from app.core.database import from_db_utc, to_db_utc
from app.modules.applications.infrastructure.models import ProjectApplicationModel
from app.modules.payments.infrastructure.models import PaymentModel
from app.modules.projects.infrastructure.models import ProjectModel
from app.modules.reviews.infrastructure.models import FreelancerReviewModel
from app.modules.workflow.domain.entities import (
    Agreement,
    ApplicationSnapshot,
    MyProjectRow,
    Party,
    PaymentSnapshot,
    ProjectParties,
    StatusHistoryEntry,
    SubmissionSnapshot,
    UserSummary,
    WorkflowProject,
)
from app.modules.workflow.domain.repositories import WorkflowRepository
from app.modules.workflow.infrastructure.models import ProjectAgreementModel, ProjectStatusHistoryModel

_RATINGS_SQL = """
    SELECT pa.freelancer_id, AVG(fr.rating) AS average_rating, COUNT(*) AS review_count
    FROM freelancer_reviews fr
    JOIN project_agreements pa ON pa.project_id = fr.project_id
    GROUP BY pa.freelancer_id
"""


def _utc(value: datetime | None) -> datetime | None:
    return from_db_utc(value) if value is not None else None


def _project(model: ProjectModel) -> WorkflowProject:
    return WorkflowProject(
        id=model.id,
        umkm_id=model.umkm_id,
        category_id=model.category_id,
        title=model.title,
        description=model.description,
        budget=int(model.budget),
        deadline=model.deadline,
        status=model.status,
        published_at=_utc(model.published_at),
        started_at=_utc(model.started_at),
        completed_at=_utc(model.completed_at),
        created_at=_utc(model.created_at),
    )


def _agreement(model: ProjectAgreementModel) -> Agreement:
    return Agreement(
        id=model.id,
        project_id=model.project_id,
        freelancer_id=model.freelancer_id,
        application_id=model.application_id,
        selection_source=model.selection_source,
        scope_of_work=model.scope_of_work,
        agreed_price=int(model.agreed_price),
        agreed_deadline=model.agreed_deadline,
        status=model.status,
        agreement_version=int(model.agreement_version),
        created_at=_utc(model.created_at),
        umkm_approved_at=_utc(model.umkm_approved_at),
        freelancer_approved_at=_utc(model.freelancer_approved_at),
        change_request_note=model.change_request_note,
        change_requested_at=_utc(model.change_requested_at),
        updated_at=_utc(model.updated_at),
    )


def _payment(model: PaymentModel) -> PaymentSnapshot:
    return PaymentSnapshot(
        id=model.id,
        status=model.status,
        fund_status=model.fund_status,
        gross_amount=int(model.gross_amount),
        platform_fee_amount=int(model.platform_fee_amount),
        freelancer_amount=int(model.freelancer_amount),
        transaction_number=model.transaction_number,
        paid_at=_utc(model.paid_at),
        released_at=_utc(model.released_at),
        expires_at=_utc(model.expires_at),
    )


def _application(model: ProjectApplicationModel) -> ApplicationSnapshot:
    return ApplicationSnapshot(
        id=model.id,
        project_id=model.project_id,
        freelancer_id=model.freelancer_id,
        proposed_price=int(model.proposed_price),
        estimated_duration_days=int(model.estimated_duration_days),
        status=model.status,
    )


def _rating(value) -> float | None:
    return round(float(value), 2) if value is not None else None


class SqlAlchemyWorkflowRepository(WorkflowRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_project(self, project_id: str, lock: bool = False) -> WorkflowProject | None:
        query = select(ProjectModel).where(ProjectModel.id == project_id)
        if lock:
            query = query.with_for_update()
        model = self._session.scalar(query.execution_options(populate_existing=True))
        return _project(model) if model else None

    def set_project_status(
        self,
        project_id: str,
        status: str,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        values: dict = {"status": status}
        if started_at is not None:
            values["started_at"] = to_db_utc(started_at)
        if completed_at is not None:
            values["completed_at"] = to_db_utc(completed_at)
        self._session.execute(
            update(ProjectModel)
            .where(ProjectModel.id == project_id)
            .values(**values)
            .execution_options(synchronize_session=False)
        )

    def add_history(self, entry: StatusHistoryEntry) -> None:
        self._session.add(
            ProjectStatusHistoryModel(
                id=entry.id,
                project_id=entry.project_id,
                previous_status=entry.previous_status,
                new_status=entry.new_status,
                action=entry.action,
                change_reason=entry.change_reason,
                change_source=entry.change_source,
                changed_by_user_id=entry.changed_by_user_id,
                changed_at=to_db_utc(entry.changed_at),
                reason_code=entry.reason_code,
            )
        )
        self._session.flush()

    def list_history(self, project_id: str) -> list[StatusHistoryEntry]:
        rows = self._session.scalars(
            select(ProjectStatusHistoryModel)
            .where(ProjectStatusHistoryModel.project_id == project_id)
            .order_by(ProjectStatusHistoryModel.changed_at, ProjectStatusHistoryModel.id)
        )
        return [
            StatusHistoryEntry(
                id=m.id,
                project_id=m.project_id,
                previous_status=m.previous_status,
                new_status=m.new_status,
                action=m.action,
                change_source=m.change_source,
                changed_at=_utc(m.changed_at),
                changed_by_user_id=m.changed_by_user_id,
                change_reason=m.change_reason,
                reason_code=m.reason_code,
            )
            for m in rows
        ]

    def get_agreement(self, project_id: str, lock: bool = False) -> Agreement | None:
        query = select(ProjectAgreementModel).where(ProjectAgreementModel.project_id == project_id)
        if lock:
            query = query.with_for_update()
        model = self._session.scalar(query.execution_options(populate_existing=True))
        return _agreement(model) if model else None

    def add_agreement(self, agreement: Agreement) -> None:
        self._session.add(
            ProjectAgreementModel(
                id=agreement.id,
                project_id=agreement.project_id,
                freelancer_id=agreement.freelancer_id,
                application_id=agreement.application_id,
                selection_source=agreement.selection_source,
                scope_of_work=agreement.scope_of_work,
                agreed_price=agreement.agreed_price,
                agreed_deadline=agreement.agreed_deadline,
                status=agreement.status,
                agreement_version=agreement.agreement_version,
                created_at=to_db_utc(agreement.created_at),
            )
        )
        self._session.flush()

    def update_agreement(self, agreement: Agreement) -> None:
        model = self._session.get(ProjectAgreementModel, agreement.id)
        model.scope_of_work = agreement.scope_of_work
        model.agreed_price = agreement.agreed_price
        model.agreed_deadline = agreement.agreed_deadline
        model.status = agreement.status
        model.agreement_version = agreement.agreement_version
        model.umkm_approved_at = to_db_utc(agreement.umkm_approved_at) if agreement.umkm_approved_at else None
        model.freelancer_approved_at = (
            to_db_utc(agreement.freelancer_approved_at) if agreement.freelancer_approved_at else None
        )
        model.change_request_note = agreement.change_request_note
        model.change_requested_at = (
            to_db_utc(agreement.change_requested_at) if agreement.change_requested_at else None
        )
        self._session.flush()

    def get_application(self, application_id: str) -> ApplicationSnapshot | None:
        model = self._session.get(ProjectApplicationModel, application_id)
        return _application(model) if model else None

    def find_application(self, project_id: str, freelancer_id: str) -> ApplicationSnapshot | None:
        model = self._session.scalar(
            select(ProjectApplicationModel).where(
                ProjectApplicationModel.project_id == project_id,
                ProjectApplicationModel.freelancer_id == freelancer_id,
            )
        )
        return _application(model) if model else None

    def set_application_status(self, application_id: str, status: str) -> None:
        self._session.execute(
            update(ProjectApplicationModel)
            .where(ProjectApplicationModel.id == application_id)
            .values(status=str(status))
            .execution_options(synchronize_session=False)
        )

    def close_submitted_applications(self, project_id: str, status: str) -> list[str]:
        condition = (
            ProjectApplicationModel.project_id == project_id,
            ProjectApplicationModel.status == "SUBMITTED",
        )
        freelancer_ids = list(
            self._session.scalars(
                select(ProjectApplicationModel.freelancer_id).where(*condition).with_for_update()
            )
        )
        if freelancer_ids:
            self._session.execute(
                update(ProjectApplicationModel)
                .where(*condition)
                .values(status=str(status))
                .execution_options(synchronize_session=False)
            )
        return freelancer_ids

    def is_freelancer(self, user_id: str) -> bool:
        row = self._session.execute(
            text(
                "SELECT 1 FROM freelancer_profiles fp JOIN users u ON u.id = fp.user_id "
                "WHERE fp.user_id = :uid AND u.role = 'FREELANCER'"
            ),
            {"uid": user_id},
        ).first()
        return row is not None

    def get_parties(self, umkm_id: str, freelancer_id: str | None) -> ProjectParties:
        umkm_row = self._session.execute(
            text(
                "SELECT u.id, u.name, u.profile_image_url, up.business_name, up.city "
                "FROM users u LEFT JOIN umkm_profiles up ON up.user_id = u.id WHERE u.id = :uid"
            ),
            {"uid": umkm_id},
        ).mappings().first()
        umkm = (
            UserSummary(
                id=umkm_row["id"],
                name=umkm_row["name"],
                subtitle=umkm_row["business_name"],
                profile_image_url=umkm_row["profile_image_url"],
                city=umkm_row["city"],
            )
            if umkm_row
            else UserSummary(id=umkm_id, name="UMKM")
        )
        freelancer = self._freelancer_summary(freelancer_id) if freelancer_id else None
        return ProjectParties(umkm=umkm, freelancer=freelancer)

    def _freelancer_summary(self, freelancer_id: str) -> UserSummary:
        row = self._session.execute(
            text(
                "SELECT u.id, u.name, u.profile_image_url, fp.professional_title, fp.city, "
                "r.average_rating, r.review_count "
                "FROM users u LEFT JOIN freelancer_profiles fp ON fp.user_id = u.id "
                f"LEFT JOIN ({_RATINGS_SQL}) r ON r.freelancer_id = u.id WHERE u.id = :uid"
            ),
            {"uid": freelancer_id},
        ).mappings().first()
        if row is None:
            return UserSummary(id=freelancer_id, name="Freelancer")
        return UserSummary(
            id=row["id"],
            name=row["name"],
            subtitle=row["professional_title"],
            profile_image_url=row["profile_image_url"],
            city=row["city"],
            average_rating=_rating(row["average_rating"]),
            review_count=int(row["review_count"] or 0),
        )

    def get_payment(self, agreement_id: str) -> PaymentSnapshot | None:
        model = self._session.scalar(
            select(PaymentModel)
            .where(PaymentModel.agreement_id == agreement_id)
            .execution_options(populate_existing=True)
        )
        return _payment(model) if model else None

    def latest_submission(self, project_id: str) -> SubmissionSnapshot | None:
        row = self._session.execute(
            text(
                "SELECT s.id, s.version_number, s.submitted_at, r.decision "
                "FROM project_submissions s LEFT JOIN submission_reviews r ON r.submission_id = s.id "
                "WHERE s.project_id = :pid ORDER BY s.version_number DESC LIMIT 1"
            ),
            {"pid": project_id},
        ).mappings().first()
        if row is None:
            return None
        return SubmissionSnapshot(
            id=row["id"],
            version_number=int(row["version_number"]),
            submitted_at=_utc(row["submitted_at"]),
            decision=row["decision"],
        )

    def count_revision_requests(self, project_id: str) -> int:
        return int(
            self._session.execute(
                text(
                    "SELECT COUNT(*) FROM submission_reviews r "
                    "JOIN project_submissions s ON s.id = r.submission_id "
                    "WHERE s.project_id = :pid AND r.decision = 'REVISION_REQUESTED'"
                ),
                {"pid": project_id},
            ).scalar_one()
        )

    def has_freelancer_review(self, project_id: str) -> bool:
        return bool(
            self._session.scalar(select(exists().where(FreelancerReviewModel.project_id == project_id)))
        )

    def _my_projects_filter(self, party: Party) -> str:
        return "p.umkm_id = :uid" if party == Party.UMKM else "a.freelancer_id = :uid"

    def list_my_projects(
        self, user_id: str, party: Party, status: str | None, limit: int, offset: int
    ) -> list[MyProjectRow]:
        where = self._my_projects_filter(party)
        if status is not None:
            where += " AND p.status = :status"
        counterpart_join = (
            "LEFT JOIN users cu ON cu.id = a.freelancer_id "
            "LEFT JOIN freelancer_profiles cfp ON cfp.user_id = a.freelancer_id "
            f"LEFT JOIN ({_RATINGS_SQL}) cr ON cr.freelancer_id = a.freelancer_id"
            if party == Party.UMKM
            else "LEFT JOIN users cu ON cu.id = p.umkm_id "
            "LEFT JOIN umkm_profiles cup ON cup.user_id = p.umkm_id"
        )
        counterpart_cols = (
            "cfp.professional_title AS cp_subtitle, cfp.city AS cp_city, "
            "cr.average_rating AS cp_rating, cr.review_count AS cp_reviews"
            if party == Party.UMKM
            else "cup.business_name AS cp_subtitle, cup.city AS cp_city, "
            "NULL AS cp_rating, NULL AS cp_reviews"
        )
        statement = text(
            f"""
            SELECT p.id AS project_id, a.id AS agreement_id, pay.id AS payment_id,
                   cu.id AS cp_id, cu.name AS cp_name, cu.profile_image_url AS cp_image, {counterpart_cols},
                   (SELECT COUNT(*) FROM project_applications pa
                     WHERE pa.project_id = p.id AND pa.status = 'SUBMITTED') AS application_count,
                   (SELECT COUNT(*) FROM project_milestones m WHERE m.project_id = p.id) AS milestone_count,
                   (SELECT COALESCE(SUM(m.weight_percent), 0) FROM project_milestones m
                     WHERE m.project_id = p.id AND m.status = 'SELESAI') AS progress
            FROM projects p
            LEFT JOIN project_agreements a ON a.project_id = p.id
            LEFT JOIN payments pay ON pay.agreement_id = a.id
            {counterpart_join}
            WHERE {where}
            ORDER BY p.updated_at DESC, p.id
            LIMIT :limit OFFSET :offset
            """
        )
        params = {"uid": user_id, "status": status, "limit": limit, "offset": offset}
        rows = self._session.execute(statement, params).mappings().all()
        if not rows:
            return []

        project_ids = [r["project_id"] for r in rows]
        projects = {
            m.id: _project(m)
            for m in self._session.scalars(select(ProjectModel).where(ProjectModel.id.in_(project_ids)))
        }
        agreements = {
            m.project_id: _agreement(m)
            for m in self._session.scalars(
                select(ProjectAgreementModel).where(ProjectAgreementModel.project_id.in_(project_ids))
            )
        }
        payment_ids = [r["payment_id"] for r in rows if r["payment_id"]]
        payments = {
            m.id: _payment(m)
            for m in self._session.scalars(select(PaymentModel).where(PaymentModel.id.in_(payment_ids)))
        } if payment_ids else {}

        result = []
        for r in rows:
            counterpart = None
            if r["cp_id"] is not None:
                counterpart = UserSummary(
                    id=r["cp_id"],
                    name=r["cp_name"],
                    subtitle=r["cp_subtitle"],
                    profile_image_url=r["cp_image"],
                    city=r["cp_city"],
                    average_rating=_rating(r["cp_rating"]),
                    review_count=int(r["cp_reviews"] or 0),
                )
            progress = None
            if int(r["milestone_count"]) > 0:
                progress = float(Decimal(str(r["progress"])))
            result.append(
                MyProjectRow(
                    project=projects[r["project_id"]],
                    agreement=agreements.get(r["project_id"]),
                    counterpart=counterpart,
                    payment=payments.get(r["payment_id"]) if r["payment_id"] else None,
                    application_count=int(r["application_count"]),
                    progress_percent=progress,
                )
            )
        return result

    def count_my_projects_by_status(self, user_id: str, party: Party) -> dict[str, int]:
        rows = self._session.execute(
            text(
                "SELECT p.status, COUNT(*) AS total FROM projects p "
                "LEFT JOIN project_agreements a ON a.project_id = p.id "
                f"WHERE {self._my_projects_filter(party)} GROUP BY p.status"
            ),
            {"uid": user_id},
        ).all()
        return {row[0]: int(row[1]) for row in rows}

