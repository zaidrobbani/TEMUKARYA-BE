from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = '3f9a1c7e2b40'
down_revision: Union[str, None] = 'c34c4e3c9286'
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


SKILLS = [
    ("logo_design", "Desain Logo"),
    ("brand_identity_design", "Desain Identitas Merek"),
    ("packaging_design", "Desain Kemasan & Label"),
    ("social_media_design", "Desain Konten Media Sosial"),
    ("promotional_design", "Desain Materi Promosi"),
    ("photography", "Fotografi"),
    ("photo_editing", "Editing Foto"),
    ("videography", "Videografi"),
    ("video_editing", "Editing Video"),
    ("motion_graphics", "Motion Graphics"),
    ("voice_over", "Voice Over"),
    ("copywriting", "Copywriting"),
    ("product_description_writing", "Penulisan Deskripsi Produk"),
    ("article_writing", "Penulisan Artikel"),
    ("video_scriptwriting", "Penulisan Naskah Video"),
    ("content_planning", "Perencanaan Konten"),
    ("social_media_management", "Pengelolaan Akun Media Sosial"),
    ("meta_ads", "Pengelolaan Iklan Instagram & Facebook"),
    ("google_ads", "Pengelolaan Google Ads"),
    ("seo", "Optimasi Mesin Pencari (SEO)"),
    ("web_design", "Desain Web"),
    ("web_programming", "Pemrograman Web"),
    ("wordpress_development", "Pembuatan Website WordPress"),
    ("website_maintenance", "Pemeliharaan Website"),
    ("marketplace_setup", "Penyiapan Toko Online"),
    ("marketplace_management", "Pengelolaan Toko Online"),
]


def upgrade() -> None:
    op.execute("ALTER TABLE users MODIFY id CHAR(36) NOT NULL DEFAULT (UUID())")
    op.execute("UPDATE users SET id = UUID()")
    op.execute("ALTER TABLE users MODIFY created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)")
    op.add_column("users", sa.Column("phone_number", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("profile_image_url", sa.String(500), nullable=True))
    op.add_column("users", timestamp("updated_at", on_update=True))

    op.create_table(
        "umkm_profiles",
        uuid_fk("user_id", "users.id", ondelete="CASCADE"),
        sa.Column("business_name", sa.String(160), nullable=False),
        sa.Column("business_category", sa.String(100), nullable=False),
        sa.Column("business_address", sa.String(300), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        timestamp("created_at"),
        timestamp("updated_at", on_update=True),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "freelancer_profiles",
        uuid_fk("user_id", "users.id", ondelete="CASCADE"),
        sa.Column("professional_title", sa.String(150), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("service_price_min", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("service_price_max", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("availability_status", sa.String(25), nullable=False, server_default="AVAILABLE"),
        timestamp("created_at"),
        timestamp("updated_at", on_update=True),
        sa.PrimaryKeyConstraint("user_id"),
        sa.CheckConstraint(
            "service_price_min IS NULL OR service_price_max IS NULL OR service_price_min <= service_price_max",
            name="ck_freelancer_profiles_price_range",
        ),
    )

    skills = op.create_table(
        "skills",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
    )
    op.bulk_insert(skills, [{"id": skill_id, "name": name} for skill_id, name in SKILLS])

    op.create_table(
        "freelancer_skills",
        uuid_fk("freelancer_id", "freelancer_profiles.user_id", ondelete="CASCADE"),
        sa.Column("skill_id", sa.String(50), sa.ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False),
        sa.PrimaryKeyConstraint("freelancer_id", "skill_id"),
    )

    op.create_table(
        "freelancer_experiences",
        uuid_pk(),
        uuid_fk("freelancer_id", "freelancer_profiles.user_id", ondelete="CASCADE"),
        sa.Column("job_title", sa.String(150), nullable=False),
        sa.Column("organization_name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        timestamp("created_at"),
        timestamp("updated_at", on_update=True),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date", name="ck_freelancer_experiences_date_range"
        ),
    )

    op.create_table(
        "portfolios",
        uuid_pk(),
        uuid_fk("freelancer_id", "freelancer_profiles.user_id", ondelete="CASCADE"),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("project_url", sa.String(1000), nullable=True),
        timestamp("created_at"),
        timestamp("updated_at", on_update=True),
    )

    op.create_table(
        "portfolio_media",
        uuid_pk(),
        uuid_fk("portfolio_id", "portfolios.id", ondelete="CASCADE"),
        *[c for c in file_columns() if c.name != "original_file_name"],
        sa.Column("sort_order", mysql.INTEGER(unsigned=True), nullable=False, server_default="0"),
        sa.Column("is_cover", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_table("portfolio_media")
    op.drop_table("portfolios")
    op.drop_table("freelancer_experiences")
    op.drop_table("freelancer_skills")
    op.drop_table("skills")
    op.drop_table("freelancer_profiles")
    op.drop_table("umkm_profiles")

    op.drop_column("users", "updated_at")
    op.drop_column("users", "profile_image_url")
    op.drop_column("users", "phone_number")
    op.execute("ALTER TABLE users MODIFY created_at DATETIME NOT NULL DEFAULT now()")
    op.execute("SET @n := 0")
    op.execute("UPDATE users SET id = (@n := @n + 1) ORDER BY created_at")
    op.execute("ALTER TABLE users MODIFY id INT NOT NULL AUTO_INCREMENT")
