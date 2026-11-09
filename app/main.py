from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import API_PREFIX, settings
from app.core.database import get_db
from app.core.error_handlers import register_error_handlers
from app.core.responses import success_response
from app.modules.admin_statistics.presentation.router import router as admin_statistics_router
from app.modules.applications.presentation.router import router as applications_router
from app.modules.auth.presentation.router import router as auth_router
from app.modules.chat.presentation.router import router as chat_router
from app.modules.discovery.presentation.router import router as discovery_router
from app.modules.enums.presentation.router import router as enums_router
from app.modules.matching.presentation.router import router as matching_router
from app.modules.milestones.presentation.router import router as milestones_router
from app.modules.profiles.presentation.router import router as profiles_router
from app.modules.projects.presentation.router import router as projects_router
from app.modules.skills.presentation.router import router as skills_router
from app.modules.users.presentation.router import router as users_router

app = FastAPI(title=settings.APP_NAME)

register_error_handlers(app)

api_router = APIRouter(prefix=API_PREFIX)


@api_router.get("/health", tags=["health"])
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return success_response("API berjalan", {"env": settings.APP_ENV, "database": "connected"})


for module_router in (
    auth_router,
    users_router,
    enums_router,
    skills_router,
    profiles_router,
    projects_router,
    applications_router,
    discovery_router,
    matching_router,
    milestones_router,
    chat_router,
    admin_statistics_router,
):
    api_router.include_router(module_router)

app.include_router(api_router)
