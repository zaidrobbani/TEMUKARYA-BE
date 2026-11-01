from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.error_handlers import register_error_handlers

# ============================================================
# MODULE ROUTERS
# ============================================================

from app.modules.users.presentation.router import (
    router as users_router,
)

from app.modules.applications.presentation.router import (
    router as applications_router,
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
)

# ============================================================
# GLOBAL ERROR HANDLERS
# ============================================================

register_error_handlers(app)


# ============================================================
# REGISTER MODULE ROUTERS
# ============================================================

app.include_router(users_router)
app.include_router(applications_router)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health", tags=["health"])
def health_check(
    db: Session = Depends(get_db),
):
    db.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "env": settings.APP_ENV,
        "database": "connected",
    }
