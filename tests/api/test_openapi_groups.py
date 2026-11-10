from app.core.config import API_PREFIX
from app.main import app
from app.openapi import GROUPS, UNGROUPED_TAG


def _operations(schema):
    return {
        f"{method.upper()} {path.removeprefix(API_PREFIX)}": operation
        for path, methods in schema["paths"].items()
        for method, operation in methods.items()
    }


def test_every_endpoint_has_a_role_group():
    operations = _operations(app.openapi())
    ungrouped = [key for key, op in operations.items() if op["tags"] == [UNGROUPED_TAG]]
    assert ungrouped == [], f"Daftarkan endpoint ini di app/openapi.py GROUPS: {ungrouped}"


def test_groups_only_reference_existing_endpoints():
    operations = _operations(app.openapi())
    stale = [op for _, _, ops in GROUPS for op in ops if op not in operations]
    assert stale == []


def test_tag_order_follows_roles():
    names = [tag["name"] for tag in app.openapi()["tags"]]
    prefixes = [name.split(" · ")[0] for name in names]
    assert prefixes[0] == "Umum"
    assert prefixes[-1] == "Admin"
    assert "UMKM" in prefixes and "Freelancer" in prefixes
    assert len(names) == len(set(names))


def test_shared_endpoint_appears_in_both_roles():
    operation = _operations(app.openapi())["POST /projects/{project_id}/agreement/approve"]
    assert "UMKM · 4. Pengajuan & Kesepakatan" in operation["tags"]
    assert "Freelancer · 3. Pengajuan & Kesepakatan" in operation["tags"]
