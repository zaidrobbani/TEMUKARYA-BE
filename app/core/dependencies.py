from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import PasswordHasher, ScryptPasswordHasher
from app.core.unit_of_work import UnitOfWork


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: Session):
        self._session = session

    def commit(self) -> None:
        self._session.commit()


def get_uow(db: Session = Depends(get_db)) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(db)


def get_password_hasher() -> PasswordHasher:
    return ScryptPasswordHasher()
