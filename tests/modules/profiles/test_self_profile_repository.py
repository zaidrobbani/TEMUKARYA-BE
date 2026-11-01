from dataclasses import replace

import pytest
from sqlalchemy import select

from app.modules.profiles.infrastructure.models import FreelancerProfileModel, UmkmProfileModel


@pytest.mark.parametrize("kind,model", [("umkm", UmkmProfileModel), ("freelancer", FreelancerProfileModel)])
def test_profile_repository_update_is_scoped_no_upsert_and_rollback(self_profile_store, kind, model):
    repositories, session, _ = self_profile_store
    repository = repositories[kind]
    own = repository.get_by_user_id("owner-1")
    foreign = repository.get_by_user_id("owner-2")
    loaded = session.get(model, "owner-1")  # Hold identity map entry to detect stale reads.
    created = loaded.created_at
    assert repository.get_by_user_id("missing") is None
    assert repository.update(replace(own, user_id="missing", city="Attack")) is None
    assert repository.get_by_user_id("missing") is None
    updated = replace(own, city="Surabaya")
    assert repository.update(updated) == updated
    assert repository.get_by_user_id("owner-1") == updated
    assert repository.update(updated) == updated  # An idempotent PUT remains successful.
    assert repository.get_by_user_id("owner-2") == foreign
    assert session.scalar(select(model.created_at).where(model.user_id == "owner-1")) == created
    session.rollback()
    assert repository.get_by_user_id("owner-1") == own
    assert repository.get_by_user_id("owner-2") == foreign


def test_freelancer_repository_replaces_nullable_fields_and_availability(self_profile_store):
    repositories, session, _ = self_profile_store
    repository = repositories["freelancer"]
    own = repository.get_by_user_id("owner-1")
    expected = replace(own, bio=None, service_price_min=None, service_price_max=None, availability_status="AVAILABLE")
    assert repository.update(expected) == expected
    session.commit()
    session.expire_all()
    assert repository.get_by_user_id("owner-1") == expected
