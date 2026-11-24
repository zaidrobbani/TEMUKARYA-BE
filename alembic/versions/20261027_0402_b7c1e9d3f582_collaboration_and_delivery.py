from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = 'b7c1e9d3f582'
down_revision: Union[str, None] = '8d2e4b6a1c93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def uuid_pk() -> sa.Column:
    return sa.Column("id", sa.CHAR(36), primary_key=True, server_default=sa.text("(UUID())"))


def uuid_fk(name: str, target: str, *, nullable: bool = False, ondelete: str = "RESTRICT") -> sa.Column:
    return sa.Column(name, sa.CHAR(36), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def timestamp(name: str, *, on_update: bool = False) -> sa.Column:
    default = "CURRENT_TIMESTAMP(3)" + (" ON UPDATE CURRENT_TIMESTAMP(3)" if on_update else "")
    return sa.Column(name, mysql.DATETIME(fsp=3), nullable=False, server_default=sa.text(default))


def file_columns() -> list[sa.Column]:
    return [
        sa.Column("original_file_name", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_size_bytes", mysql.BIGINT(unsigned=True), nullable=False),
        timestamp("uploaded_at"),
    ]


def upgrade() -> None:
    op.create_table(
        "project_agreements",
        uuid_pk(),
        uuid_fk("project_id", "projects.id"),
        uuid_fk("freelancer_id", "freelancer_profiles.user_id"),
        uuid_fk("application_id", "project_applications.id", nullable=True),
        sa.Column("selection_source", sa.String(30), nullable=False),
        sa.Column("scope_of_work", sa.Text(), nullable=False),
        sa.Column("agreed_price", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("agreed_deadline", sa.Date(), nullable=False),
        sa.Column("status", sa.String(35), nullable=False, server_default="PENDING_APPROVAL"),
        sa.Column("agreement_version", mysql.INTEGER(unsigned=True), nullable=False, server_default="1"),
        sa.Column("umkm_approved_at", mysql.DATETIME(fsp=3), nullable=True),
        sa.Column("freelancer_approved_at", mysql.DATETIME(fsp=3), nullable=True),
        timestamp("created_at"),
        timestamp("updated_at", on_update=True),
        sa.UniqueConstraint("project_id", name="uq_project_agreements_project"),
        sa.CheckConstraint("agreed_price > 0", name="ck_project_agreements_price_positive"),
        sa.CheckConstraint(
            "(selection_source = 'APPLICATION') = (application_id IS NOT NULL)",
            name="ck_project_agreements_application_source",
        ),
    )

    op.create_table(
        "project_milestones",
        uuid_pk(),
        uuid_fk("project_id", "projects.id"),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("weight_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("status", sa.String(25), nullable=False, server_default="BELUM_SELESAI"),
        sa.Column("sort_order", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("completed_at", mysql.DATETIME(fsp=3), nullable=True),
        uuid_fk("updated_by_user_id", "users.id", nullable=True),
        timestamp("created_at"),
        timestamp("updated_at", on_update=True),
        sa.UniqueConstraint("project_id", "sort_order", name="uq_project_milestones_project_order"),
        sa.CheckConstraint(
            "weight_percent > 0 AND weight_percent <= 100", name="ck_project_milestones_weight_range"
        ),
    )

    op.create_table(
        "project_status_history",
        uuid_pk(),
        uuid_fk("project_id", "projects.id"),
        sa.Column("previous_status", sa.String(40), nullable=True),
        sa.Column("new_status", sa.String(40), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("change_source", sa.String(15), nullable=False, server_default="USER"),
        uuid_fk("changed_by_user_id", "users.id", nullable=True),
        timestamp("changed_at"),
    )
    op.create_index(
        "ix_project_status_history_project_changed_at", "project_status_history", ["project_id", "changed_at"]
    )

    op.create_table(
        "project_submissions",
        uuid_pk(),
        uuid_fk("project_id", "projects.id"),
        sa.Column("version_number", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("submission_note", sa.Text(), nullable=True),
        sa.Column("result_url", sa.String(1000), nullable=True),
        timestamp("submitted_at"),
        sa.UniqueConstraint("project_id", "version_number", name="uq_project_submissions_project_version"),
    )

    op.create_table(
        "submission_files",
        uuid_pk(),
        uuid_fk("submission_id", "project_submissions.id", ondelete="CASCADE"),
        *file_columns(),
    )

    op.create_table(
        "submission_reviews",
        uuid_pk(),
        uuid_fk("submission_id", "project_submissions.id"),
        uuid_fk("reviewer_user_id", "users.id"),
        sa.Column("decision", sa.String(25), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        timestamp("reviewed_at"),
        sa.UniqueConstraint("submission_id", name="uq_submission_reviews_submission"),
        sa.CheckConstraint(
            "decision <> 'REVISION_REQUESTED' OR (review_note IS NOT NULL AND review_note <> '')",
            name="ck_submission_reviews_revision_note",
        ),
    )

    op.create_table(
        "freelancer_reviews",
        uuid_pk(),
        uuid_fk("project_id", "projects.id"),
        sa.Column("rating", mysql.TINYINT(unsigned=True), nullable=False),
        sa.Column("review_text", sa.Text(), nullable=True),
        timestamp("created_at"),
        sa.UniqueConstraint("project_id", name="uq_freelancer_reviews_project"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_freelancer_reviews_rating_range"),
    )


def downgrade() -> None:
    op.drop_table("freelancer_reviews")
    op.drop_table("submission_reviews")
    op.drop_table("submission_files")
    op.drop_table("project_submissions")
    op.drop_table("project_status_history")
    op.drop_table("project_milestones")
    op.drop_table("project_agreements")
