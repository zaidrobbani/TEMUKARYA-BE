from dataclasses import replace

import pytest


def test_list_experiences_filters_owner_and_orders_newest_first(experience_store):
    repository, _ = experience_store
    assert [item.id for item in repository.list_by_freelancer_id("owner-1")] == [
        "own-newer", "own-older",
    ]
    assert repository.list_by_freelancer_id("no-experiences") == []


def test_update_experience_persists_and_accepts_unchanged_values(experience_store):
    repository, uow = experience_store
    original = repository.list_by_freelancer_id("owner-1")[0]
    updated = replace(original, job_title="Senior Designer")
    assert repository.update(updated) is True
    uow.commit()
    assert repository.list_by_freelancer_id("owner-1")[0] == updated
    assert repository.update(updated) is True


@pytest.mark.parametrize("target_id", ["foreign", "missing"])
def test_update_experience_cannot_write_foreign_or_missing_id(experience_store, target_id):
    repository, uow = experience_store
    foreign_before = repository.list_by_freelancer_id("owner-2")
    own_before = repository.list_by_freelancer_id("owner-1")
    assert repository.update(replace(own_before[0], id=target_id)) is False
    uow.commit()
    assert repository.list_by_freelancer_id("owner-2") == foreign_before
    assert repository.list_by_freelancer_id("owner-1") == own_before


@pytest.mark.parametrize("target_id", ["foreign", "missing"])
def test_delete_experience_cannot_remove_foreign_or_missing_id(experience_store, target_id):
    repository, uow = experience_store
    foreign_before = repository.list_by_freelancer_id("owner-2")
    own_before = repository.list_by_freelancer_id("owner-1")
    assert repository.delete(target_id, "owner-1") is False
    uow.commit()
    assert repository.list_by_freelancer_id("owner-2") == foreign_before
    assert repository.list_by_freelancer_id("owner-1") == own_before


def test_delete_experience_removes_only_target(experience_store):
    repository, uow = experience_store
    assert repository.delete("own-newer", "owner-1") is True
    uow.commit()
    assert repository.delete("own-newer", "owner-1") is False
    assert [item.id for item in repository.list_by_freelancer_id("owner-1")] == ["own-older"]
    assert [item.id for item in repository.list_by_freelancer_id("owner-2")] == ["foreign"]
