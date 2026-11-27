from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)

from app.modules.matching.application.dto import (
    FreelancerRecommendationsPage,
    ProjectRecommendationsPage,
    RecommendFreelancersInput,
    RecommendProjectsInput,
)

from app.modules.matching.domain.entities import (
    FreelancerRecommendation,
    ProjectRecommendation,
)

from app.modules.matching.domain.repositories import (
    MatchingRepository,
)

from app.modules.matching.domain.scoring import (
    calculate_skill_match,
)


MAX_LIMIT = 100
MAX_OFFSET = 10000
MAX_ID_LENGTH = 36


def _normalize_id(
    value: str,
    name: str,
) -> str:
    if not isinstance(value, str):
        raise BadRequestError(
            f"{name} harus berupa string"
        )

    normalized = value.strip()

    if (
        not normalized
        or len(normalized) > MAX_ID_LENGTH
    ):
        raise BadRequestError(
            f"{name} tidak valid"
        )

    return normalized


def _validate_pagination(
    limit: int,
    offset: int,
) -> None:
    if (
        type(limit) is not int
        or not 1 <= limit <= MAX_LIMIT
    ):
        raise BadRequestError(
            "Limit harus antara 1 dan 100"
        )

    if (
        type(offset) is not int
        or not 0 <= offset <= MAX_OFFSET
    ):
        raise BadRequestError(
            "Offset harus antara 0 dan 10000"
        )


class RecommendFreelancersForProject:
    def __init__(
        self,
        repository: MatchingRepository,
    ):
        self._repository = repository

    def execute(
        self,
        data: RecommendFreelancersInput,
    ) -> FreelancerRecommendationsPage:
        _validate_pagination(
            data.limit,
            data.offset,
        )

        project_id = _normalize_id(
            data.project_id,
            "Project ID",
        )

        umkm_id = _normalize_id(
            data.umkm_id,
            "UMKM ID",
        )

        project = self._repository.get_project(
            project_id
        )

        if (
            project is None
            or project.umkm_id != umkm_id
        ):
            raise NotFoundError(
                "Project tidak ditemukan"
            )

        if project.status != "TERBUKA":
            raise ConflictError(
                "Rekomendasi hanya tersedia "
                "untuk project TERBUKA"
            )

        matches: list[
            FreelancerRecommendation
        ] = []

        seen: set[str] = set()

        if project.required_skill_ids:
            candidates = (
                self._repository
                .iter_available_freelancers()
            )

            for freelancer in candidates:
                if freelancer.freelancer_id in seen:
                    continue

                seen.add(
                    freelancer.freelancer_id
                )

                if (
                    freelancer.availability_status
                    != "AVAILABLE"
                ):
                    continue

                match = calculate_skill_match(
                    project.required_skill_ids,
                    freelancer.skill_ids,
                )

                if match.meets_threshold:
                    matches.append(
                        FreelancerRecommendation(
                            freelancer=freelancer,
                            match=match,
                        )
                    )

        matches.sort(
            key=lambda item: (
                -item.match.score_percent,
                -item.match.matched_count,
                item.freelancer.name.casefold(),
                item.freelancer.freelancer_id,
            )
        )

        page = matches[
            data.offset:
            data.offset + data.limit
        ]

        return FreelancerRecommendationsPage(
            project_id=project_id,
            items=tuple(page),
            limit=data.limit,
            offset=data.offset,
            has_more=(
                len(matches)
                > data.offset + data.limit
            ),
        )


class RecommendProjectsForFreelancer:
    def __init__(
        self,
        repository: MatchingRepository,
    ):
        self._repository = repository

    def execute(
        self,
        data: RecommendProjectsInput,
    ) -> ProjectRecommendationsPage:
        _validate_pagination(
            data.limit,
            data.offset,
        )

        freelancer_id = _normalize_id(
            data.freelancer_id,
            "Freelancer ID",
        )

        freelancer = (
            self._repository.get_freelancer(
                freelancer_id
            )
        )

        if freelancer is None:
            raise NotFoundError(
                "Profil Freelancer tidak ditemukan"
            )

        matches: list[
            ProjectRecommendation
        ] = []

        seen: set[str] = set()

        if freelancer.skill_ids:
            candidates = (
                self._repository
                .iter_published_projects()
            )

            for project in candidates:
                if project.project_id in seen:
                    continue

                seen.add(
                    project.project_id
                )

                if project.status != "TERBUKA":
                    continue

                if not project.required_skill_ids:
                    continue

                match = calculate_skill_match(
                    project.required_skill_ids,
                    freelancer.skill_ids,
                )

                if match.meets_threshold:
                    matches.append(
                        ProjectRecommendation(
                            project=project,
                            match=match,
                        )
                    )

        matches.sort(
            key=lambda item: (
                -item.match.score_percent,
                -item.match.matched_count,
                item.project.title.casefold(),
                item.project.project_id,
            )
        )

        page = matches[
            data.offset:
            data.offset + data.limit
        ]

        return ProjectRecommendationsPage(
            freelancer_id=freelancer_id,
            items=tuple(page),
            limit=data.limit,
            offset=data.offset,
            has_more=(
                len(matches)
                > data.offset + data.limit
            ),
        )
