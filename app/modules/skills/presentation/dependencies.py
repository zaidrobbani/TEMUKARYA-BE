from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.skills.application.use_cases import (
    ListMasterData,
)
from app.modules.skills.infrastructure.repositories import (
    SqlAlchemyMasterDataRepository,
)


def get_master_data_use_case(
    db: Session = Depends(get_db),
) -> ListMasterData:

    repository = SqlAlchemyMasterDataRepository(db)

    return ListMasterData(repository)