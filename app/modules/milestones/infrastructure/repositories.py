from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError

from app.modules.milestones.domain.entities import (
    Milestone,
    MilestoneStatus,
)

from app.modules.milestones.domain.repositories import (
    ProjectMilestoneContext,
)


def _parse_date(
    value: date | str,
) -> date:
    if isinstance(value, date):
        return value

    return date.fromisoformat(value)


def _parse_datetime(
    value: datetime | str | None,
) -> datetime | None:
    if value is None or isinstance(
        value,
        datetime,
    ):
        return value

    return datetime.fromisoformat(value)


class SqlAlchemyMilestoneRepository:
    def __init__(
        self,
        session: Session,
    ):
        self._session = session

    def get_project_context(
        self,
        project_id: str,
    ) -> ProjectMilestoneContext | None:
        statement = text("""
            SELECT
                id,
                umkm_id,
                status,
                started_at,
                deadline

            FROM projects

            WHERE id = :project_id
        """)

        row = self._session.execute(
            statement,
            {
                "project_id": project_id,
            },
        ).mappings().one_or_none()

        if row is None:
            return None

        return ProjectMilestoneContext(
            project_id=str(row["id"]),
            umkm_id=str(row["umkm_id"]),
            status=str(row["status"]),
            started_at=_parse_datetime(
                row["started_at"]
            ),
            deadline=_parse_date(
                row["deadline"]
            ),

            freelancer_id=None,
        )

    def list_milestones(
        self,
        project_id: str,
    ) -> tuple[Milestone, ...]:
        statement = text("""
            SELECT
                id,
                project_id,
                name,
                description,
                weight_percent,
                status,
                sort_order,
                completed_at,
                updated_by_user_id

            FROM project_milestones

            WHERE project_id = :project_id

            ORDER BY
                sort_order ASC,
                id ASC
        """)

        rows = self._session.execute(
            statement,
            {
                "project_id": project_id,
            },
        ).mappings().all()

        return tuple(
            Milestone(
                id=str(row["id"]),
                project_id=str(row["project_id"]),
                name=row["name"],
                description=row["description"],
                weight_percent=Decimal(
                    str(row["weight_percent"])
                ),
                status=MilestoneStatus(
                    row["status"]
                ),
                sort_order=int(
                    row["sort_order"]
                ),
                completed_at=_parse_datetime(
                    row["completed_at"]
                ),
                updated_by_user_id=(
                    str(row["updated_by_user_id"])
                    if row["updated_by_user_id"] is not None
                    else None
                ),
            )
            for row in rows
        )

    def get_total_weight(
        self,
        project_id: str,
    ) -> Decimal:
        statement = text("""
            SELECT weight_percent

            FROM project_milestones

            WHERE project_id = :project_id
        """)

        rows = self._session.execute(
            statement,
            {
                "project_id": project_id,
            },
        ).scalars().all()

        return sum(
            (
                Decimal(str(weight))
                for weight in rows
            ),
            Decimal("0.00"),
        )

    def replace_plan_and_reset_approvals(
        self,
        project_id: str,
        milestones: tuple[Milestone, ...],
    ) -> None:
        raise ConflictError(
            "Workflow approval-reset belum "
            "terintegrasi; perubahan rencana ditolak"
        )

    def complete_if_pending(
        self,
        project_id: str,
        milestone_id: str,
        updated_by_user_id: str,
        completed_at: datetime,
    ) -> bool:
        if completed_at.tzinfo is not None:
            completed_at = (
                completed_at
                .astimezone(timezone.utc)
                .replace(tzinfo=None)
            )

        statement = text("""
            UPDATE project_milestones

            SET
                status = 'SELESAI',
                completed_at = :completed_at,
                updated_by_user_id = :updated_by_user_id

            WHERE project_id = :project_id

              AND id = :milestone_id

              AND status = 'BELUM_SELESAI'
        """)

        result = self._session.execute(
            statement,
            {
                "completed_at": completed_at,
                "updated_by_user_id": (
                    updated_by_user_id
                ),
                "project_id": project_id,
                "milestone_id": milestone_id,
            },
        )

        return result.rowcount == 1
