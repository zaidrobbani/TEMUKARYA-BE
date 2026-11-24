from app.core.exceptions import BadRequestError, ConflictError
from app.modules.profiles.application.dto import CreateFreelancerProfileInput
from app.modules.profiles.domain.entities import FreelancerProfile
from app.modules.profiles.domain.repositories import FreelancerProfileRepository
from app.core.unit_of_work import UnitOfWork
from app.core.exceptions import NotFoundError
from app.modules.profiles.application.profile_validation import (
    freelancer_profile, umkm_profile,
    validate_text_capacity as _validate_text_capacity,
)

from uuid import uuid4
from ipaddress import ip_address
import re
from urllib.parse import urlsplit

from app.core.exceptions import (
    BadRequestError,
    NotFoundError,
)

from app.modules.profiles.application.dto import (
    CreateFreelancerExperienceInput,
    UpdateFreelancerExperienceInput,
    CreatePortfolioInput,
    UpdatePortfolioInput,
    PortfolioPage,
)

from app.modules.profiles.domain.entities import (
    FreelancerExperience,
    Portfolio,
)

from app.modules.profiles.domain.repositories import (
    FreelancerExperienceRepository,
    PortfolioRepository,
)

from app.modules.profiles.application.dto import (
    SetFreelancerSkillsInput,
)

from app.modules.profiles.domain.repositories import (
    FreelancerSkillsRepository,
)

from app.modules.profiles.application.dto import (
    CreateUmkmProfileInput,
)
from app.modules.profiles.domain.entities import (
    UmkmProfile,
)
from app.modules.profiles.domain.repositories import (
    UmkmProfileRepository,
)


class CreateUmkmProfile:

    def __init__(
        self,
        repository: UmkmProfileRepository,
        uow: UnitOfWork,
    ):
        self._repository = repository
        self._uow = uow

    def execute(
        self,
        user_id: str,
        data: CreateUmkmProfileInput,
    ) -> UmkmProfile:

        # Cek apakah pengguna sudah mempunyai profil
        existing_profile = self._repository.get_by_user_id(
            user_id
        )

        if existing_profile is not None:
            raise ConflictError(
                "Profil UMKM sudah terdaftar"
            )

        profile = umkm_profile(user_id, data)

        # Menyimpan dan melakukan commit transaksi
        saved_profile = self._repository.add(profile)
        self._uow.commit()

        return saved_profile



class CreateFreelancerProfile:

    def __init__(
        self,
        repository: FreelancerProfileRepository,
        uow: UnitOfWork,
    ):
        self._repository = repository
        self._uow = uow

    def execute(
        self,
        user_id: str,
        data: CreateFreelancerProfileInput,
    ) -> FreelancerProfile:

        # 1. Cek apakah profil freelancer sudah ada
        existing_profile = self._repository.get_by_user_id(
            user_id
        )

        if existing_profile is not None:
            raise ConflictError(
                "Profil Freelancer sudah terdaftar"
            )

        profile = freelancer_profile(user_id, data)

        # 6. Simpan melalui repository
        saved_profile = self._repository.add(profile)

        # 7. Commit transaksi
        self._uow.commit()

        return saved_profile


class SetFreelancerSkills:

    def __init__(
        self,
        profile_repository: FreelancerProfileRepository,
        skills_repository: FreelancerSkillsRepository,
        uow: UnitOfWork,
    ):
        self._profile_repository = profile_repository
        self._skills_repository = skills_repository
        self._uow = uow

    def execute(
        self,
        freelancer_id: str,
        data: SetFreelancerSkillsInput,
    ) -> list[str]:

        # 1. Pastikan profil Freelancer tersedia
        profile = self._profile_repository.get_by_user_id(
            freelancer_id
        )

        if profile is None:
            raise NotFoundError(
                "Profil Freelancer tidak ditemukan"
            )

        # 2. Validasi daftar ID keahlian
        skill_ids = data.skill_ids

        if any(
            not isinstance(skill_id, str)
            or not skill_id
            or skill_id != skill_id.strip()
            for skill_id in skill_ids
        ):
            raise BadRequestError(
                "ID keahlian tidak valid"
            )

        # 3. Cegah skill duplikat
        if len(skill_ids) != len(set(skill_ids)):
            raise BadRequestError(
                "Keahlian tidak boleh duplikat"
            )

        # 4. Pastikan semua skill ada di master data
        existing_ids = (
            self._skills_repository.get_existing_skill_ids(
                skill_ids
            )
        )

        invalid_ids = set(skill_ids) - existing_ids

        if invalid_ids:
            raise BadRequestError(
                "Terdapat ID keahlian yang tidak tersedia"
            )

        # 5. Ganti daftar skill Freelancer
        self._skills_repository.replace_skills(
            freelancer_id,
            skill_ids,
        )

        # 6. Simpan perubahan transaksi
        self._uow.commit()

        return skill_ids


    
class GetFreelancerSkills:

    def __init__(
        self,
        profile_repository: FreelancerProfileRepository,
        skills_repository: FreelancerSkillsRepository,
    ):
        self._profile_repository = profile_repository
        self._skills_repository = skills_repository

    def execute(
        self,
        freelancer_id: str,
    ) -> list[str]:

        # 1. Periksa apakah profil Freelancer ada
        profile = self._profile_repository.get_by_user_id(
            freelancer_id
        )

        if profile is None:
            raise NotFoundError(
                "Profil Freelancer tidak ditemukan"
            )

        # 2. Ambil daftar keahlian dari repository
        skill_ids = self._skills_repository.get_skill_ids(
            freelancer_id
        )

        # 3. Kembalikan hasilnya
        return skill_ids


class CreateFreelancerExperience:

    def __init__(
        self,
        profile_repository: FreelancerProfileRepository,
        experience_repository: FreelancerExperienceRepository,
        uow: UnitOfWork,
    ):
        self._profile_repository = profile_repository
        self._experience_repository = experience_repository
        self._uow = uow

    def execute(
        self,
        freelancer_id: str,
        data: CreateFreelancerExperienceInput,
    ) -> FreelancerExperience:

        # 1. Memastikan profil Freelancer tersedia
        profile = self._profile_repository.get_by_user_id(
            freelancer_id
        )

        if profile is None:
            raise NotFoundError(
                "Profil Freelancer tidak ditemukan"
            )

        experience = _validated_experience(
            experience_id=str(uuid4()),
            freelancer_id=freelancer_id,
            data=data,
        )

        # 8. Menyimpan melalui repository
        self._experience_repository.add(experience)

        # 9. Commit transaksi
        self._uow.commit()

        # 10. Mengembalikan hasil
        return experience


def _validated_experience(
    experience_id: str,
    freelancer_id: str,
    data: CreateFreelancerExperienceInput,
) -> FreelancerExperience:
    """Aturan yang sama untuk membuat dan mengganti pengalaman kerja."""
    job_title = data.job_title.strip()
    organization_name = data.organization_name.strip()
    description = data.description.strip()

    if not job_title or len(job_title) > 150:
        raise BadRequestError(
            "Judul pekerjaan wajib diisi dan maksimal 150 karakter"
        )
    if not organization_name or len(organization_name) > 160:
        raise BadRequestError(
            "Nama organisasi wajib diisi dan maksimal 160 karakter"
        )
    if not description:
        raise BadRequestError("Deskripsi pengalaman wajib diisi")
    _validate_text_capacity(description, "Deskripsi pengalaman")
    if data.end_date is not None and data.end_date < data.start_date:
        raise BadRequestError(
            "Tanggal selesai tidak boleh sebelum tanggal mulai"
        )

    return FreelancerExperience(
        id=experience_id,
        freelancer_id=freelancer_id,
        job_title=job_title,
        organization_name=organization_name,
        description=description,
        start_date=data.start_date,
        end_date=data.end_date,
    )


class GetFreelancerExperiences:
    def __init__(self, experience_repository: FreelancerExperienceRepository):
        self._experience_repository = experience_repository

    def execute(self, freelancer_id: str) -> list[FreelancerExperience]:
        return self._experience_repository.list_by_freelancer_id(freelancer_id)


class UpdateFreelancerExperience:
    def __init__(
        self,
        experience_repository: FreelancerExperienceRepository,
        uow: UnitOfWork,
    ):
        self._experience_repository = experience_repository
        self._uow = uow

    def execute(
        self,
        freelancer_id: str,
        experience_id: str,
        data: UpdateFreelancerExperienceInput,
    ) -> FreelancerExperience:
        experience = _validated_experience(experience_id, freelancer_id, data)
        if not self._experience_repository.update(experience):
            raise NotFoundError("Pengalaman kerja tidak ditemukan")
        self._uow.commit()
        return experience


class DeleteFreelancerExperience:
    def __init__(
        self,
        experience_repository: FreelancerExperienceRepository,
        uow: UnitOfWork,
    ):
        self._experience_repository = experience_repository
        self._uow = uow

    def execute(self, freelancer_id: str, experience_id: str) -> None:
        if not self._experience_repository.delete(experience_id, freelancer_id):
            raise NotFoundError("Pengalaman kerja tidak ditemukan")
        self._uow.commit()


def _validated_project_url(value: str | None) -> str | None:
    """URL metadata HTTP(S); tidak melakukan request jaringan atau DNS lookup."""
    if value is None:
        return None
    value = value.strip()
    try:
        if not value or len(value) > 1000:
            raise ValueError
        if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError
        if any(char in value for char in '\\<>"') or re.search(r"%(?![0-9a-fA-F]{2})", value):
            raise ValueError
        value.encode("utf-8")
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host:
            raise ValueError
        if parsed.username is not None or parsed.password is not None:
            raise ValueError
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError
        if parsed.netloc.endswith(":"):
            raise ValueError
        if ":" in host or re.fullmatch(r"[0-9.]+", host):
            ip_address(host)
        else:
            ascii_host = host.encode("idna").decode("ascii").rstrip(".")
            if len(ascii_host) > 253 or not all(
                re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
                for label in ascii_host.split(".")
            ):
                raise ValueError
    except (ValueError, UnicodeError):
        raise BadRequestError(
            "project_url harus URL HTTP/HTTPS dengan host valid, tanpa kredensial, "
            "dan maksimal 1000 karakter"
        ) from None
    return value


def _validated_portfolio(
    portfolio_id: str, freelancer_id: str, data: CreatePortfolioInput,
) -> Portfolio:
    title = data.title.strip()
    description = data.description.strip()
    if not title or len(title) > 180:
        raise BadRequestError("Judul portfolio wajib diisi dan maksimal 180 karakter")
    _validate_text_capacity(title, "Judul portfolio")
    if not description:
        raise BadRequestError("Deskripsi portfolio wajib diisi")
    _validate_text_capacity(description, "Deskripsi portfolio")
    return Portfolio(
        id=portfolio_id, freelancer_id=freelancer_id, title=title,
        description=description, project_url=_validated_project_url(data.project_url),
    )


class CreatePortfolio:
    def __init__(
        self, profile_repository: FreelancerProfileRepository,
        portfolio_repository: PortfolioRepository, uow: UnitOfWork,
    ):
        self._profile_repository = profile_repository
        self._portfolio_repository = portfolio_repository
        self._uow = uow

    def execute(self, freelancer_id: str, data: CreatePortfolioInput) -> Portfolio:
        if self._profile_repository.get_by_user_id(freelancer_id) is None:
            raise NotFoundError("Profil Freelancer tidak ditemukan")
        portfolio = _validated_portfolio(str(uuid4()), freelancer_id, data)
        saved = self._portfolio_repository.add(portfolio)
        self._uow.commit()
        return saved


class GetPortfolios:
    def __init__(self, portfolio_repository: PortfolioRepository):
        self._portfolio_repository = portfolio_repository

    def execute(self, freelancer_id: str, limit: int = 20, offset: int = 0) -> PortfolioPage:
        if type(limit) is not int or type(offset) is not int:
            raise BadRequestError("Pagination harus berupa integer")
        if not 1 <= limit <= 100 or not 0 <= offset <= 10000:
            raise BadRequestError("limit harus 1-100 dan offset harus 0-10000")
        items = self._portfolio_repository.list_by_freelancer_id(
            freelancer_id, limit + 1, offset,
        )
        return PortfolioPage(items=items[:limit], limit=limit, offset=offset, has_more=len(items) > limit)


class GetPortfolio:
    def __init__(self, portfolio_repository: PortfolioRepository):
        self._portfolio_repository = portfolio_repository

    def execute(self, freelancer_id: str, portfolio_id: str) -> Portfolio:
        portfolio = self._portfolio_repository.get_by_id(portfolio_id, freelancer_id)
        if portfolio is None:
            raise NotFoundError("Portfolio tidak ditemukan")
        return portfolio


class UpdatePortfolio:
    def __init__(self, portfolio_repository: PortfolioRepository, uow: UnitOfWork):
        self._portfolio_repository = portfolio_repository
        self._uow = uow

    def execute(
        self, freelancer_id: str, portfolio_id: str, data: UpdatePortfolioInput,
    ) -> Portfolio:
        portfolio = _validated_portfolio(portfolio_id, freelancer_id, data)
        saved = self._portfolio_repository.update(portfolio)
        if saved is None:
            raise NotFoundError("Portfolio tidak ditemukan")
        self._uow.commit()
        return saved


class DeletePortfolio:
    def __init__(self, portfolio_repository: PortfolioRepository, uow: UnitOfWork):
        self._portfolio_repository = portfolio_repository
        self._uow = uow

    def execute(self, freelancer_id: str, portfolio_id: str) -> None:
        if not self._portfolio_repository.delete(portfolio_id, freelancer_id):
            raise NotFoundError("Portfolio tidak ditemukan")
        self._uow.commit()
