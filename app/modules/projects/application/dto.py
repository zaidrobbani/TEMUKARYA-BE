from dataclasses import dataclass
from datetime import date

from app.modules.projects.domain.entities import Project

@dataclass(frozen=True)
class CreateProjectInput:
    category_id: str
    title: str
    description: str
    budget: int
    deadline: date
    skill_ids: tuple[str, ...]


@dataclass(frozen=True)
class UpdateProjectInput:
    category_id: str
    title: str
    description: str
    budget: int
    deadline: date
    skill_ids: tuple[str, ...]


@dataclass(frozen=True)
class PublicProjectsPage:
    items: tuple[Project, ...]
    limit: int
    offset: int
    has_more: bool
