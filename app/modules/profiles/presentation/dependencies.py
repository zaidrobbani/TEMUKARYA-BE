from fastapi import Depends
import os
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_uow
from app.core.unit_of_work import UnitOfWork
from app.modules.profiles.application.self_profile_use_cases import (
    GetUmkmProfile, GetFreelancerProfile, UpdateUmkmProfile, UpdateFreelancerProfile,
)

from app.modules.profiles.domain.repositories import (
    UmkmProfileRepository,
)
from app.modules.profiles.application.use_cases import (
    CreateUmkmProfile,
)
from app.modules.profiles.infrastructure.repositories import (
    SqlAlchemyUmkmProfileRepository,
)

from app.modules.profiles.domain.repositories import (
    FreelancerProfileRepository,
)
from app.modules.profiles.application.use_cases import (
    CreateFreelancerProfile,
)
from app.modules.profiles.infrastructure.repositories import (
    SqlAlchemyFreelancerProfileRepository,
)

from app.modules.profiles.application.use_cases import (
    SetFreelancerSkills,
)

from app.modules.profiles.domain.repositories import (
    FreelancerSkillsRepository,
)

from app.modules.profiles.infrastructure.repositories import (
    SqlAlchemyFreelancerSkillsRepository,
)

from app.modules.profiles.application.use_cases import (
    GetFreelancerSkills,
)

from app.modules.profiles.application.use_cases import (
    CreateFreelancerExperience,
    GetFreelancerExperiences,
    UpdateFreelancerExperience,
    DeleteFreelancerExperience,
)

from app.modules.profiles.domain.repositories import (
    FreelancerExperienceRepository,
)

from app.modules.profiles.infrastructure.repositories import (
    SqlAlchemyFreelancerExperienceRepository,
    SqlAlchemyPortfolioRepository,
)

from app.modules.profiles.domain.repositories import PortfolioRepository
from app.modules.profiles.application.use_cases import (
    CreatePortfolio, GetPortfolios, GetPortfolio, UpdatePortfolio, DeletePortfolio,
)
from app.modules.profiles.application.media_use_cases import PortfolioMediaService, DeletePortfolioWithMedia
from app.modules.profiles.infrastructure.media_repository import SqlAlchemyMediaRepository
from app.modules.profiles.infrastructure.media_storage import LocalImageStorage


def get_umkm_profile_repository(
    db: Session = Depends(get_db),
) -> UmkmProfileRepository:

    return SqlAlchemyUmkmProfileRepository(db)


def create_umkm_profile_use_case(
    repository: UmkmProfileRepository = Depends(
        get_umkm_profile_repository
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> CreateUmkmProfile:

    return CreateUmkmProfile(
        repository=repository,
        uow=uow,
    )



def get_freelancer_profile_repository(
    db: Session = Depends(get_db),
) -> FreelancerProfileRepository:

    return SqlAlchemyFreelancerProfileRepository(db)


def create_freelancer_profile_use_case(
    repository: FreelancerProfileRepository = Depends(
        get_freelancer_profile_repository
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> CreateFreelancerProfile:

    return CreateFreelancerProfile(
        repository=repository,
        uow=uow,
    )



def get_umkm_profile_use_case(
    repository: UmkmProfileRepository = Depends(get_umkm_profile_repository),
) -> GetUmkmProfile:
    return GetUmkmProfile(repository)


def update_umkm_profile_use_case(
    repository: UmkmProfileRepository = Depends(get_umkm_profile_repository),
    uow: UnitOfWork = Depends(get_uow),
) -> UpdateUmkmProfile:
    return UpdateUmkmProfile(repository, uow)


def get_freelancer_profile_use_case(
    repository: FreelancerProfileRepository = Depends(get_freelancer_profile_repository),
) -> GetFreelancerProfile:
    return GetFreelancerProfile(repository)


def update_freelancer_profile_use_case(
    repository: FreelancerProfileRepository = Depends(get_freelancer_profile_repository),
    uow: UnitOfWork = Depends(get_uow),
) -> UpdateFreelancerProfile:
    return UpdateFreelancerProfile(repository, uow)


def get_freelancer_skills_repository(
    db: Session = Depends(get_db),
) -> FreelancerSkillsRepository:

    return SqlAlchemyFreelancerSkillsRepository(db)


def set_freelancer_skills_use_case(
    profile_repository: FreelancerProfileRepository = Depends(
        get_freelancer_profile_repository
    ),
    skills_repository: FreelancerSkillsRepository = Depends(
        get_freelancer_skills_repository
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> SetFreelancerSkills:

    return SetFreelancerSkills(
        profile_repository=profile_repository,
        skills_repository=skills_repository,
        uow=uow,
    )


def get_freelancer_skills_use_case(
    profile_repository: FreelancerProfileRepository = Depends(
        get_freelancer_profile_repository
    ),
    skills_repository: FreelancerSkillsRepository = Depends(
        get_freelancer_skills_repository
    ),
) -> GetFreelancerSkills:

    return GetFreelancerSkills(
        profile_repository=profile_repository,
        skills_repository=skills_repository,
    )

# FREELANCER EXPERIENCE DEPENDENCIES

def get_freelancer_experience_repository(
    db: Session = Depends(get_db),
) -> FreelancerExperienceRepository:

    return SqlAlchemyFreelancerExperienceRepository(db)


def create_freelancer_experience_use_case(
    profile_repository: FreelancerProfileRepository = Depends(
        get_freelancer_profile_repository
    ),
    experience_repository: FreelancerExperienceRepository = Depends(
        get_freelancer_experience_repository
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> CreateFreelancerExperience:

    return CreateFreelancerExperience(
        profile_repository=profile_repository,
        experience_repository=experience_repository,
        uow=uow,
    )


def get_freelancer_experiences_use_case(
    experience_repository: FreelancerExperienceRepository = Depends(
        get_freelancer_experience_repository
    ),
) -> GetFreelancerExperiences:
    return GetFreelancerExperiences(experience_repository=experience_repository)


def update_freelancer_experience_use_case(
    experience_repository: FreelancerExperienceRepository = Depends(
        get_freelancer_experience_repository
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> UpdateFreelancerExperience:
    return UpdateFreelancerExperience(
        experience_repository=experience_repository,
        uow=uow,
    )


def delete_freelancer_experience_use_case(
    experience_repository: FreelancerExperienceRepository = Depends(
        get_freelancer_experience_repository
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> DeleteFreelancerExperience:
    return DeleteFreelancerExperience(
        experience_repository=experience_repository,
        uow=uow,
    )


def get_portfolio_repository(db: Session = Depends(get_db)) -> PortfolioRepository:
    return SqlAlchemyPortfolioRepository(db)


def create_portfolio_use_case(
    profile_repository: FreelancerProfileRepository = Depends(get_freelancer_profile_repository),
    portfolio_repository: PortfolioRepository = Depends(get_portfolio_repository),
    uow: UnitOfWork = Depends(get_uow),
) -> CreatePortfolio:
    return CreatePortfolio(profile_repository, portfolio_repository, uow)


def get_portfolios_use_case(
    portfolio_repository: PortfolioRepository = Depends(get_portfolio_repository),
) -> GetPortfolios:
    return GetPortfolios(portfolio_repository)


def get_portfolio_use_case(
    portfolio_repository: PortfolioRepository = Depends(get_portfolio_repository),
) -> GetPortfolio:
    return GetPortfolio(portfolio_repository)


def update_portfolio_use_case(
    portfolio_repository: PortfolioRepository = Depends(get_portfolio_repository),
    uow: UnitOfWork = Depends(get_uow),
) -> UpdatePortfolio:
    return UpdatePortfolio(portfolio_repository, uow)


def get_media_repository(db: Session = Depends(get_db)):
    return SqlAlchemyMediaRepository(db)


def get_portfolio_storage():
    return LocalImageStorage(os.environ.get("PORTFOLIO_STORAGE_ROOT", "/app/storage/portfolios"))


def get_media_service(
    repository=Depends(get_media_repository), storage=Depends(get_portfolio_storage),
    uow: UnitOfWork = Depends(get_uow),
):
    return PortfolioMediaService(repository, storage, uow)


def delete_portfolio_use_case(service=Depends(get_media_service)) -> DeletePortfolioWithMedia:
    return DeletePortfolioWithMedia(service)
