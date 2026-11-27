from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.modules.projects.infrastructure.owner_reader import ProjectOwner, SqlProjectOwnerReader
from app.modules.projects.presentation.router import _with_owners


def project(pid, umkm_id):
    return SimpleNamespace(id=pid, umkm_id=umkm_id, category_id="graphic_design", title="T", description="D",
                           budget=1000, deadline=date(2026, 12, 20), status="TERBUKA", published_at=None,
                           started_at=None, completed_at=None, created_at=None, updated_at=None)


class FakeReader:
    def owners(self, ids):
        return {"u1": ProjectOwner("u1", "Izah", "Kedai Kopi", "Malang", "/api/v1/users/u1/photo?v=1")}

    def skill_ids(self, ids):
        return {"p1": ["copywriting", "logo_design"]}


def test_with_owners_fills_known_owner_and_leaves_unknown_empty():
    items = _with_owners([project("p1", "u1"), project("p2", "u2")], FakeReader())
    assert items[0].umkm.business_name == "Kedai Kopi"
    assert items[0].umkm.owner_name == "Izah" and items[0].umkm.city == "Malang"
    assert items[1].umkm is None
    assert items[0].skill_ids == ["copywriting", "logo_design"] and items[1].skill_ids == []


def test_reader_joins_users_and_umkm_profiles():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    with engine.begin() as c:
        c.execute(text("CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT, profile_image_url TEXT)"))
        c.execute(text("CREATE TABLE umkm_profiles (user_id TEXT PRIMARY KEY, business_name TEXT, city TEXT)"))
        c.execute(text("INSERT INTO users VALUES ('u1','Izah','/p'),('u2','Tanpa Profil',NULL)"))
        c.execute(text("INSERT INTO umkm_profiles VALUES ('u1','Kedai Kopi','Malang')"))
    owners = SqlProjectOwnerReader(Session(engine)).owners(["u1", "u2", "u1", "u3"])
    assert owners["u1"] == ProjectOwner("u1", "Izah", "Kedai Kopi", "Malang", "/p")
    assert owners["u2"].business_name is None and owners["u2"].owner_name == "Tanpa Profil"
    assert "u3" not in owners
    assert SqlProjectOwnerReader(Session(engine)).owners([]) == {}


def test_selected_freelancer_can_view_non_open_project():
    from app.core.exceptions import NotFoundError
    from app.modules.projects.application.use_cases import GetProjectDetail
    import pytest

    p = project("p1", "u1")
    p.status = "MENUNGGU_KESEPAKATAN"
    p.published_at = object()
    repo = SimpleNamespace(get_by_id=lambda pid: p if pid == "p1" else None)
    use_case = GetProjectDetail(repo, is_selected_freelancer=lambda pid, uid: uid == "f-terpilih")
    assert use_case.execute("p1", "f-terpilih") is p
    assert use_case.execute("p1", "u1") is p
    with pytest.raises(NotFoundError):
        use_case.execute("p1", "f-lain")
    with pytest.raises(NotFoundError):
        GetProjectDetail(repo).execute("p1", "f-terpilih")
