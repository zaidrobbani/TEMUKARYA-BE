from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.presentation.dependencies import get_current_user

from app.modules.milestones.application.dto import (
    MilestoneActor,
)

from app.modules.milestones.infrastructure.repositories import (
    SqlAlchemyMilestoneRepository,
)

from app.modules.milestones.infrastructure.workflow_repository import WorkflowMilestoneRepository
from app.modules.users.domain.entities import User
from app.modules.workflow.application.services import ApprovalResetter
from app.modules.workflow.infrastructure.repositories import SqlAlchemyWorkflowRepository


def get_authenticated_milestone_actor(
    user: Annotated[User, Depends(get_current_user)],
) -> MilestoneActor:
    return MilestoneActor(user_id=user.id, role=user.role)


def get_milestone_repository(
    session: Annotated[Session, Depends(get_db)],
) -> SqlAlchemyMilestoneRepository:
    resetter = ApprovalResetter(SqlAlchemyWorkflowRepository(session))
    return WorkflowMilestoneRepository(session, resetter.reset)


def get_milestone_today() -> date:
    return datetime.now(
        timezone.utc
    ).date()
