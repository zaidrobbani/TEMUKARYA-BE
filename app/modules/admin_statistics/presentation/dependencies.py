from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.modules.auth.presentation.dependencies import get_current_user

from app.modules.admin_statistics.domain.entities import (
    AdminActor,
)

from app.modules.admin_statistics.infrastructure.repositories import (
    SqlAlchemyAdminStatisticsRepository,
)

from app.modules.users.domain.entities import User


def get_authenticated_admin_actor(
    user: Annotated[User, Depends(get_current_user)],
) -> AdminActor:
    return AdminActor(user_id=user.id, role=user.role)


def get_admin_statistics_repository(
    session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> SqlAlchemyAdminStatisticsRepository:
    return SqlAlchemyAdminStatisticsRepository(
        session=session,
    )
