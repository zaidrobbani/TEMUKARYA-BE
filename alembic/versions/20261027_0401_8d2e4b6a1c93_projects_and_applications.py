"""projects and applications: categories, projects, project skills, attachments, applications

Revision ID: 8d2e4b6a1c93
Revises: 3f9a1c7e2b40
Create Date: 2026-10-27 04:01:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = '8d2e4b6a1c93'
down_revision: Union[str, None] = '3f9a1c7e2b40'
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


# Diturunkan dari daftar kebutuhan digital UMKM di PRD (Blueprint 1.2). Boleh diubah tim lewat migrasi baru.
CATEGORIES = [
    ("website", "Website", "Pembuatan, desain, dan pemeliharaan website"),
    ("graphic_design", "Desain Grafis", "Logo, identitas merek, kemasan, dan materi promosi"),
    ("content_creation", "Pembuatan Konten", "Konten foto, video, dan tulisan untuk promosi"),
    ("digital_marketing", "Digital Marketing", "Iklan berbayar, SEO, dan strategi pemasaran digital"),
    ("social_media_management", "Pengelolaan Media Sosial", "Perencanaan dan pengelolaan akun media sosial"),
    ("product_photography", "Fotografi Produk", "Foto dan video produk untuk katalog atau toko online"),
    ("other_technology", "Teknologi Lainnya", "Kebutuhan teknologi lain, misalnya penyiapan toko online"),
]


def upgrade() -> None:
    categories = op.create_table(
        "project_categories",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.String(400), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )
    op.bulk_insert(
        categories,
        [{"id": cid, "name": name, "description": desc, "is_active": True} for cid, name, desc in CATEGORIES],
    )

    op.create_table(
        "projects",
        uuid_pk(),
        uuid_fk("umkm_id", "umkm_profiles.user_id"),
        sa.Column(
            "category_id", sa.String(50), sa.ForeignKey("project_categories.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        # Budget estimasi dari form UMKM; harga final ada di project_agreements.agreed_price
        sa.Column("budget", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=False),
        # Diisi TERBUKA saat publish; perubahan berikutnya hanya lewat modul workflow
        sa.Column("status", sa.String(40), nullable=False, server_default="TERBUKA"),
        sa.Column("published_at", mysql.DATETIME(fsp=3), nullable=True),
        sa.Column("started_at", mysql.DATETIME(fsp=3), nullable=True),
        sa.Column("completed_at", mysql.DATETIME(fsp=3), nullable=True),
        timestamp("created_at"),
        timestamp("updated_at", on_update=True),
        sa.CheckConstraint("budget > 0", name="ck_projects_budget_positive"),
    )
    # Untuk daftar project TERBUKA terbaru (marketplace & rekomendasi)
    op.create_index("ix_projects_status_published_at", "projects", ["status", "published_at"])

    op.create_table(
        "project_skills",
        uuid_fk("project_id", "projects.id", ondelete="CASCADE"),
        sa.Column("skill_id", sa.String(50), sa.ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False),
        sa.PrimaryKeyConstraint("project_id", "skill_id"),
    )

    op.create_table(
        "project_attachments",
        uuid_pk(),
        uuid_fk("project_id", "projects.id", ondelete="CASCADE"),
        *file_columns(),
    )

    op.create_table(
        "project_applications",
        uuid_pk(),
        uuid_fk("project_id", "projects.id"),
        uuid_fk("freelancer_id", "freelancer_profiles.user_id"),
        sa.Column("proposed_price", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("estimated_duration_days", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("proposal_message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="SUBMITTED"),
        timestamp("submitted_at"),
        timestamp("created_at"),
        timestamp("updated_at", on_update=True),
        # Satu freelancer hanya boleh melamar sekali per project
        sa.UniqueConstraint("project_id", "freelancer_id", name="uq_project_applications_project_freelancer"),
        sa.CheckConstraint("proposed_price > 0", name="ck_project_applications_price_positive"),
        sa.CheckConstraint("estimated_duration_days > 0", name="ck_project_applications_duration_positive"),
    )


def downgrade() -> None:
    op.drop_table("project_applications")
    op.drop_table("project_attachments")
    op.drop_table("project_skills")
    op.drop_table("projects")
    op.drop_table("project_categories")
