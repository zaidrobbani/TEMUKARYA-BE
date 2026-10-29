from collections.abc import Generator
from datetime import datetime
from typing import Annotated
from uuid import uuid4

from sqlalchemy import CHAR, FetchedValue, create_engine, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase, Session, mapped_column, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


UuidPk = Annotated[
    str,
    mapped_column(
        CHAR(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("(UUID())"),
    ),
]

CreatedAt = Annotated[
    datetime,
    mapped_column(
        mysql.DATETIME(fsp=3),
        server_default=text("CURRENT_TIMESTAMP(3)"),
    ),
]

UpdatedAt = Annotated[
    datetime,
    mapped_column(
        mysql.DATETIME(fsp=3),
        server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"),
        server_onupdate=FetchedValue(),
    ),
]


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
