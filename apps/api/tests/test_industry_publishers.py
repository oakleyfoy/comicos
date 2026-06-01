from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.industry_publisher import IndustryPublisher
from app.services.industry_publisher_registry import INDUSTRY_PUBLISHER_REGISTRY
from app.services.industry_publisher_scan_config import included_publishers_for_scan, list_industry_publishers
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    from app.models import User

    user = session.exec(select(User).where(User.email == email)).first()
    assert user is not None and user.id is not None
    return int(user.id)


def test_industry_publisher_seed_on_list(client: TestClient, session: Session) -> None:
    email = "ind-pub-seed@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)

    items = list_industry_publishers(session, owner_user_id=owner_id)
    assert len(items) == len(INDUSTRY_PUBLISHER_REGISTRY)
    codes = {row.publisher_code for row in items}
    assert codes == {code for code, _, _ in INDUSTRY_PUBLISHER_REGISTRY}
    assert all(row.inclusion_status == "INCLUDED" for row in items)
    assert all(row.scan_enabled for row in items)


def test_included_publishers_for_scan_excludes_disabled(client: TestClient, session: Session) -> None:
    email = "ind-pub-scan@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    items = list_industry_publishers(session, owner_user_id=owner_id)
    marvel = next(row for row in items if row.publisher_code == "MARVEL")

    from app.services.industry_publisher_scan_config import update_industry_publisher
    from app.schemas.industry_publisher import IndustryPublisherUpdate

    update_industry_publisher(
        session,
        owner_user_id=owner_id,
        publisher_id=marvel.id,
        update=IndustryPublisherUpdate(inclusion_status="EXCLUDED"),
    )
    included = included_publishers_for_scan(session, owner_user_id=owner_id)
    assert all(row.publisher_code != "MARVEL" for row in included)
    assert len(included) == len(INDUSTRY_PUBLISHER_REGISTRY) - 1


def test_industry_publishers_api_list_and_patch(client: TestClient, session: Session) -> None:
    email = "ind-pub-api@example.com"
    token = register_and_login(client, email)

    listed = client.get("/api/v1/industry-publishers", headers=auth_headers(token))
    assert listed.status_code == 200
    data = listed.json()["data"]
    assert data["total_items"] == len(INDUSTRY_PUBLISHER_REGISTRY)
    dc = next(item for item in data["items"] if item["publisher_code"] == "DC")

    patched = client.patch(
        f"/api/v1/industry-publishers/{dc['id']}",
        headers=auth_headers(token),
        json={"scan_enabled": False, "scan_priority": 15},
    )
    assert patched.status_code == 200
    body = patched.json()["data"]
    assert body["scan_enabled"] is False
    assert body["scan_priority"] == 15

    excluded = client.patch(
        f"/api/v1/industry-publishers/{dc['id']}",
        headers=auth_headers(token),
        json={"inclusion_status": "EXCLUDED"},
    )
    assert excluded.status_code == 200
    assert excluded.json()["data"]["inclusion_status"] == "EXCLUDED"
    assert excluded.json()["data"]["scan_enabled"] is False

    row = session.exec(select(IndustryPublisher).where(IndustryPublisher.id == dc["id"])).first()
    assert row is not None
    assert row.inclusion_status == "EXCLUDED"


def test_industry_publishers_patch_not_found(client: TestClient) -> None:
    token = register_and_login(client, "ind-pub-404@example.com")
    resp = client.patch(
        "/api/v1/industry-publishers/999999",
        headers=auth_headers(token),
        json={"scan_enabled": True},
    )
    assert resp.status_code == 404
