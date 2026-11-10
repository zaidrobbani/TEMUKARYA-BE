from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.presentation.dependencies import get_current_user
from app.modules.users.domain.entities import User
from app.modules.workflow.application.dto import Actor
from app.modules.workflow.domain.repositories import WorkflowRepository
from app.modules.workflow.infrastructure.repositories import SqlAlchemyWorkflowRepository


def get_actor(user: User = Depends(get_current_user)) -> Actor:
    return Actor(user_id=user.id, role=user.role)


def get_workflow_repository(db: Session = Depends(get_db)) -> WorkflowRepository:
    return SqlAlchemyWorkflowRepository(db)
