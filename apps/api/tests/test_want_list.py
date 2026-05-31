from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.want_list import DEFAULT_WANT_LIST_NAME, WantListItem
from app.services.want_list_hooks import (
    sync_acquisition_opportunities,
    sync_marketplace_matches,
    sync_missing_issues,
)
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_default_want_list_on_list(client: TestClient, session: Session) -> None:
    email = "wl-default@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    resp = client.get("/api/v1/want-lists", headers=auth_headers(token))
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["name"] == DEFAULT_WANT_LIST_NAME
    assert items[0]["owner_id"] == owner_id
    assert items[0]["is_active"] is True


def test_create_list_add_update_delete_item(client: TestClient, session: Session) -> None:
    email = "wl-crud@example.com"
    token = register_and_login(client, email)
    lists = client.get("/api/v1/want-lists", headers=auth_headers(token))
    list_id = lists.json()["data"]["items"][0]["id"]

    created = client.post(
        "/api/v1/want-lists",
        headers=auth_headers(token),
        json={"name": "Grails", "description": "High priority"},
    )
    assert created.status_code == 200
    grails_id = created.json()["data"]["id"]

    add = client.post(
        f"/api/v1/want-lists/{grails_id}/items",
        headers=auth_headers(token),
        json={
            "publisher": "Image",
            "series_name": "Battle Beast",
            "issue_number": "3",
            "priority": "CRITICAL",
            "notes": "Need for run",
        },
    )
    assert add.status_code == 200
    item = add.json()["data"]
    assert item["series_name"] == "Battle Beast"
    assert item["issue_number"] == "3"
    assert item["priority"] == "CRITICAL"
    item_id = item["id"]

    detail = client.get(f"/api/v1/want-lists/{grails_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    assert len(detail.json()["data"]["items"]) == 1

    patch = client.patch(
        f"/api/v1/want-list-items/{item_id}",
        headers=auth_headers(token),
        json={"status": "FOUND", "notes": "Spotted at shop"},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["status"] == "FOUND"

    delete = client.delete(f"/api/v1/want-list-items/{item_id}", headers=auth_headers(token))
    assert delete.status_code == 200
    detail2 = client.get(f"/api/v1/want-lists/{grails_id}", headers=auth_headers(token))
    assert detail2.json()["data"]["items"] == []

    rows = session.exec(select(WantListItem).where(WantListItem.id == item_id)).all()
    assert rows == []


def test_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "wl-a@example.com")
    token_b = register_and_login(client, "wl-b@example.com")
    list_a = client.get("/api/v1/want-lists", headers=auth_headers(token_a)).json()["data"]["items"][0]["id"]
    forbidden = client.get(f"/api/v1/want-lists/{list_a}", headers=auth_headers(token_b))
    assert forbidden.status_code == 404


def test_patch_want_list(client: TestClient) -> None:
    token = register_and_login(client, "wl-patch@example.com")
    list_id = client.get("/api/v1/want-lists", headers=auth_headers(token)).json()["data"]["items"][0]["id"]
    patched = client.patch(
        f"/api/v1/want-lists/{list_id}",
        headers=auth_headers(token),
        json={"description": "Updated default list"},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["description"] == "Updated default list"


def test_future_hooks_not_implemented(session: Session) -> None:
    import pytest

    for fn in (sync_missing_issues, sync_marketplace_matches, sync_acquisition_opportunities):
        with pytest.raises(NotImplementedError):
            fn(session, owner_user_id=1)
