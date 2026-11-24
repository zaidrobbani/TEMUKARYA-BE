from app.core.exceptions import NotFoundError
from app.core.unit_of_work import UnitOfWork
from app.modules.profiles.application.dto import UpdateFreelancerProfileInput, UpdateUmkmProfileInput
from app.modules.profiles.application.profile_validation import freelancer_profile, umkm_profile
from app.modules.profiles.domain.entities import FreelancerProfile, UmkmProfile
from app.modules.profiles.domain.repositories import FreelancerProfileRepository, UmkmProfileRepository


class GetUmkmProfile:
    def __init__(self, repository: UmkmProfileRepository):
        self._repository = repository

    def execute(self, user_id: str) -> UmkmProfile:
        profile = self._repository.get_by_user_id(user_id)
        if profile is None:
            raise NotFoundError("Profil UMKM tidak ditemukan")
        return profile


class GetFreelancerProfile:
    def __init__(self, repository: FreelancerProfileRepository):
        self._repository = repository

    def execute(self, user_id: str) -> FreelancerProfile:
        profile = self._repository.get_by_user_id(user_id)
        if profile is None:
            raise NotFoundError("Profil Freelancer tidak ditemukan")
        return profile


class UpdateUmkmProfile:
    def __init__(self, repository: UmkmProfileRepository, uow: UnitOfWork):
        self._repository = repository
        self._uow = uow

    def execute(self, user_id: str, data: UpdateUmkmProfileInput) -> UmkmProfile:
        GetUmkmProfile(self._repository).execute(user_id)
        saved = self._repository.update(umkm_profile(user_id, data))
        if saved is None:
            raise NotFoundError("Profil UMKM tidak ditemukan")
        self._uow.commit()
        return saved


class UpdateFreelancerProfile:
    def __init__(self, repository: FreelancerProfileRepository, uow: UnitOfWork):
        self._repository = repository
        self._uow = uow

    def execute(self, user_id: str, data: UpdateFreelancerProfileInput) -> FreelancerProfile:
        GetFreelancerProfile(self._repository).execute(user_id)
        saved = self._repository.update(freelancer_profile(user_id, data, data.availability_status))
        if saved is None:
            raise NotFoundError("Profil Freelancer tidak ditemukan")
        self._uow.commit()
        return saved
