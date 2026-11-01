from sqlalchemy.orm import Session
from sqlalchemy import text, bindparam, select, update, delete

from app.modules.profiles.domain.entities import (
    UmkmProfile,
    FreelancerProfile,
    FreelancerExperience,
    Portfolio,
)

from app.modules.profiles.infrastructure.models import (
    UmkmProfileModel,
    FreelancerProfileModel,
    FreelancerExperienceModel,
    PortfolioModel,
)


class SqlAlchemyUmkmProfileRepository:

    def __init__(self, session: Session):
        self._session = session

    def update(self, profile: UmkmProfile) -> UmkmProfile | None:
        result = self._session.execute(
            update(UmkmProfileModel).where(UmkmProfileModel.user_id == profile.user_id).values(
                business_name=profile.business_name, business_category=profile.business_category,
                business_address=profile.business_address, city=profile.city,
            )
        )
        # No upsert; MySQL audit columns remain entirely server-managed.
        return profile if result.rowcount else None

    def get_by_user_id(
        self,
        user_id: str,
    ) -> UmkmProfile | None:

        model = self._session.get(
            UmkmProfileModel,
            user_id,
        )

        if model is None:
            return None

        return self._to_entity(model)

    def add(
        self,
        profile: UmkmProfile,
    ) -> UmkmProfile:

        model = UmkmProfileModel(
            user_id=profile.user_id,
            business_name=profile.business_name,
            business_category=profile.business_category,
            business_address=profile.business_address,
            city=profile.city,
        )

        self._session.add(model)

        return profile

    @staticmethod
    def _to_entity(
        model: UmkmProfileModel,
    ) -> UmkmProfile:

        return UmkmProfile(
            user_id=model.user_id,
            business_name=model.business_name,
            business_category=model.business_category,
            business_address=model.business_address,
            city=model.city,
        )



class SqlAlchemyFreelancerProfileRepository:

    def __init__(self, session: Session):
        self._session = session

    def update(self, profile: FreelancerProfile) -> FreelancerProfile | None:
        result = self._session.execute(
            update(FreelancerProfileModel).where(FreelancerProfileModel.user_id == profile.user_id).values(
                professional_title=profile.professional_title, city=profile.city, bio=profile.bio,
                service_price_min=profile.service_price_min, service_price_max=profile.service_price_max,
                availability_status=profile.availability_status,
            )
        )
        return profile if result.rowcount else None

    def get_by_user_id(
        self,
        user_id: str,
    ) -> FreelancerProfile | None:

        model = self._session.get(
            FreelancerProfileModel,
            user_id,
        )

        if model is None:
            return None

        return self._to_entity(model)

    def add(
        self,
        profile: FreelancerProfile,
    ) -> FreelancerProfile:

        model = FreelancerProfileModel(
            user_id=profile.user_id,
            professional_title=profile.professional_title,
            bio=profile.bio,
            city=profile.city,
            service_price_min=profile.service_price_min,
            service_price_max=profile.service_price_max,
            availability_status=profile.availability_status,
        )

        self._session.add(model)

        return profile

    @staticmethod
    def _to_entity(
        model: FreelancerProfileModel,
    ) -> FreelancerProfile:

        return FreelancerProfile(
            user_id=model.user_id,
            professional_title=model.professional_title,
            bio=model.bio,
            city=model.city,
            service_price_min=model.service_price_min,
            service_price_max=model.service_price_max,
            availability_status=model.availability_status,
        )


class SqlAlchemyFreelancerSkillsRepository:

    def __init__(self, session: Session):
        self._session = session

    # 1. Mengambil semua skill milik Freelancer
    def get_skill_ids(
        self,
        freelancer_id: str,
    ) -> list[str]:

        query = text("""
            SELECT skill_id
            FROM freelancer_skills
            WHERE freelancer_id = :freelancer_id
            ORDER BY skill_id
        """)

        result = self._session.execute(
            query,
            {"freelancer_id": freelancer_id},
        )

        return list(result.scalars().all())

    # 2. Memeriksa skill yang tersedia di master data
    def get_existing_skill_ids(
        self,
        skill_ids: list[str],
    ) -> set[str]:

        if not skill_ids:
            return set()

        query = text("""
            SELECT id
            FROM skills
            WHERE id IN :skill_ids
        """).bindparams(
            bindparam("skill_ids", expanding=True)
        )

        result = self._session.execute(
            query,
            {"skill_ids": skill_ids},
        )

        return set(result.scalars().all())

    # 3. Mengganti seluruh daftar skill Freelancer
    def replace_skills(
        self,
        freelancer_id: str,
        skill_ids: list[str],
    ) -> None:

        # Hapus daftar skill sebelumnya
        delete_query = text("""
            DELETE FROM freelancer_skills
            WHERE freelancer_id = :freelancer_id
        """)

        self._session.execute(
            delete_query,
            {"freelancer_id": freelancer_id},
        )

        # Tambahkan daftar skill terbaru
        if skill_ids:
            insert_query = text("""
                INSERT INTO freelancer_skills (
                    freelancer_id,
                    skill_id
                )
                VALUES (
                    :freelancer_id,
                    :skill_id
                )
            """)

            rows = [
                {
                    "freelancer_id": freelancer_id,
                    "skill_id": skill_id,
                }
                for skill_id in skill_ids
            ]

            self._session.execute(
                insert_query,
                rows,
            )


# FREELANCER EXPERIENCE REPOSITORY

class SqlAlchemyFreelancerExperienceRepository:

    def __init__(self, session: Session):
        self._session = session

    def list_by_freelancer_id(
        self, freelancer_id: str,
    ) -> list[FreelancerExperience]:
        models = self._session.scalars(
            select(FreelancerExperienceModel)
            .where(FreelancerExperienceModel.freelancer_id == freelancer_id)
            .order_by(
                FreelancerExperienceModel.start_date.desc(),
                FreelancerExperienceModel.id,
            )
        ).all()
        return [self._to_entity(model) for model in models]

    def update(self, experience: FreelancerExperience) -> bool:
        result = self._session.execute(
            update(FreelancerExperienceModel)
            .where(
                FreelancerExperienceModel.id == experience.id,
                FreelancerExperienceModel.freelancer_id == experience.freelancer_id,
            )
            .values(
                job_title=experience.job_title,
                organization_name=experience.organization_name,
                description=experience.description,
                start_date=experience.start_date,
                end_date=experience.end_date,
            )
        )
        return result.rowcount == 1

    def delete(self, experience_id: str, freelancer_id: str) -> bool:
        result = self._session.execute(
            delete(FreelancerExperienceModel).where(
                FreelancerExperienceModel.id == experience_id,
                FreelancerExperienceModel.freelancer_id == freelancer_id,
            )
        )
        return result.rowcount == 1

    @staticmethod
    def _to_entity(model: FreelancerExperienceModel) -> FreelancerExperience:
        return FreelancerExperience(
            id=model.id,
            freelancer_id=model.freelancer_id,
            job_title=model.job_title,
            organization_name=model.organization_name,
            description=model.description,
            start_date=model.start_date,
            end_date=model.end_date,
        )

    def add(
        self,
        experience: FreelancerExperience,
    ) -> None:

        model = FreelancerExperienceModel(
            id=experience.id,
            freelancer_id=experience.freelancer_id,
            job_title=experience.job_title,
            organization_name=experience.organization_name,
            description=experience.description,
            start_date=experience.start_date,
            end_date=experience.end_date,
        )

        self._session.add(model)


class SqlAlchemyPortfolioRepository:
    def __init__(self, session: Session):
        self._session = session

    def add(self, portfolio: Portfolio) -> Portfolio:
        model = PortfolioModel(
            id=portfolio.id, freelancer_id=portfolio.freelancer_id,
            title=portfolio.title, description=portfolio.description,
            project_url=portfolio.project_url,
        )
        self._session.add(model)
        self._session.flush()
        # Tanggal berasal dari database; repository tidak melakukan commit.
        self._session.refresh(model)
        return self._to_entity(model)

    def list_by_freelancer_id(
        self, freelancer_id: str, limit: int, offset: int,
    ) -> list[Portfolio]:
        models = self._session.scalars(
            select(PortfolioModel)
            .where(PortfolioModel.freelancer_id == freelancer_id)
            .order_by(PortfolioModel.created_at.desc(), PortfolioModel.id)
            .limit(limit).offset(offset)
        ).all()
        return [self._to_entity(model) for model in models]

    def get_by_id(self, portfolio_id: str, freelancer_id: str) -> Portfolio | None:
        model = self._session.scalar(
            select(PortfolioModel).where(
                PortfolioModel.id == portfolio_id,
                PortfolioModel.freelancer_id == freelancer_id,
            ).execution_options(populate_existing=True)
        )
        return self._to_entity(model) if model is not None else None

    def update(self, portfolio: Portfolio) -> Portfolio | None:
        result = self._session.execute(
            update(PortfolioModel).where(
                PortfolioModel.id == portfolio.id,
                PortfolioModel.freelancer_id == portfolio.freelancer_id,
            ).values(
                title=portfolio.title, description=portfolio.description,
                project_url=portfolio.project_url,
            ).execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            return None
        return self.get_by_id(portfolio.id, portfolio.freelancer_id)

    def delete(self, portfolio_id: str, freelancer_id: str) -> bool:
        result = self._session.execute(
            delete(PortfolioModel).where(
                PortfolioModel.id == portfolio_id,
                PortfolioModel.freelancer_id == freelancer_id,
            )
        )
        return result.rowcount == 1

    @staticmethod
    def _to_entity(model: PortfolioModel) -> Portfolio:
        return Portfolio(
            id=model.id, freelancer_id=model.freelancer_id,
            title=model.title, description=model.description, project_url=model.project_url,
            created_at=model.created_at, updated_at=model.updated_at,
        )
