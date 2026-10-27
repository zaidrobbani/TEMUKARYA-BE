from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    id: str
    name: str


@dataclass(frozen=True)
class ProjectCategory:
    id: str
    name: str
    description: str
    is_active: bool