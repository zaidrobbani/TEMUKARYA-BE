"""Profile column constraints shared by create and replace use cases."""

from app.core.exceptions import BadRequestError
from app.modules.profiles.application.dto import CreateFreelancerProfileInput, CreateUmkmProfileInput
from app.modules.profiles.domain.entities import FreelancerProfile, UmkmProfile


def validate_text_capacity(value: str, field: str) -> None:
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        raise BadRequestError(f"{field} harus berupa teks UTF-8 yang valid") from None
    if len(encoded) > 65535:
        raise BadRequestError(f"{field} maksimal 65535 byte UTF-8")


def required_text(value: str, field: str, limit: int) -> str:
    value = value.strip()
    if not value or len(value) > limit:
        raise BadRequestError(f"{field} tidak valid")
    validate_text_capacity(value, field)
    return value


def umkm_profile(user_id: str, data: CreateUmkmProfileInput) -> UmkmProfile:
    return UmkmProfile(
        user_id=user_id,
        business_name=required_text(data.business_name, "business_name", 160),
        business_category=required_text(data.business_category, "business_category", 100),
        business_address=required_text(data.business_address, "business_address", 300),
        city=required_text(data.city, "city", 100),
    )


def freelancer_profile(
    user_id: str, data: CreateFreelancerProfileInput, availability_status: str = "AVAILABLE",
) -> FreelancerProfile:
    title = required_text(data.professional_title, "professional_title", 150)
    city = required_text(data.city, "city", 100)
    availability = required_text(availability_status, "availability_status", 25)
    bio = (data.bio.strip() or None) if data.bio is not None else None
    if bio is not None:
        validate_text_capacity(bio, "bio")
    for field in ("service_price_min", "service_price_max"):
        value = getattr(data, field)
        if value is not None and (type(value) is not int or not 0 <= value <= 18446744073709551615):
            raise BadRequestError(f"{field} harus berupa bilangan bulat BIGINT UNSIGNED")
    if (data.service_price_min is not None and data.service_price_max is not None
            and data.service_price_min > data.service_price_max):
        raise BadRequestError("Harga minimum tidak boleh lebih besar dari harga maksimum")
    return FreelancerProfile(
        user_id=user_id, professional_title=title, city=city, bio=bio,
        service_price_min=data.service_price_min, service_price_max=data.service_price_max,
        availability_status=availability,
    )
