from sqlalchemy import Boolean, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Master data dibaca lewat SQL mentah; model ini dibutuhkan agar FK
# projects.category_id & project_skills.skill_id bisa di-resolve ORM.
class SkillModel(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)


class ProjectCategoryModel(Base):
    __tablename__ = "project_categories"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(400), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
