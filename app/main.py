from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.error_handlers import register_error_handlers
from app.core.responses import success_response
from app.modules.auth.presentation.router import router as auth_router
from app.modules.enums.presentation.router import router as enums_router
from app.modules.users.presentation.router import router as users_router
from app.modules.skills.presentation.router import router as skills_router
from app.modules.profiles.presentation.router import router as profiles_router
from app.modules.projects.presentation.router import router as projects_router
from app.modules.applications.presentation.router import router as applications_router
from app.modules.discovery.presentation.router import router as discovery_router
from app.modules.matching.presentation.router import router as matching_router

app = FastAPI(title=settings.APP_NAME)

register_error_handlers(app)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(enums_router)
app.include_router(skills_router)
app.include_router(profiles_router)
app.include_router(projects_router)
app.include_router(applications_router)
app.include_router(discovery_router)
app.include_router(matching_router)


@app.get("/health", tags=["health"])
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return success_response("API berjalan", {"env": settings.APP_ENV, "database": "connected"})
