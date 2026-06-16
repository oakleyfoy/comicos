from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.catalog_p97 import ComicVineVolumeUniverse
from test_inventory import auth_headers, register_and_login


def _create_acq(client: TestClient, token: str) -> int:
    resp = client.post(
        "/api/v1/acquisitions",
        headers=auth_headers(token),
        json={
            "acquisition_type": "FACEBOOK",
            "purchase_date": "2026-06-01",
            "seller_name": "Lot",
            "total_paid": "350.22",
            "shipping_paid": "0.00",
            "tax_paid": "0.00",
        },
    )
    assert resp.status_code == 200, resp.text
    return int(resp.json()["id"])


def _seed_volume(session: Session) -> None:
    session.add(
        ComicVineVolumeUniverse(
            volume_id=12345,
            name="Uncanny X-Men",
            publisher="Marvel",
            start_year=1963,
            count_of_issues=500,
        )
    )
    session.commit()


def test_create_placeholder_from_tree_issue(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "tree1@test.com")
    _seed_volume(session)
    acq_id = _create_acq(client, token)
    resp = client.post(
        f"/api/v1/acquisitions/{acq_id}/placeholder-items/tree",
        headers=auth_headers(token),
        json={
            "publisher": "Marvel",
            "volume_id": 12345,
            "issue_number": "221",
            "quantity": 1,
            "source_issue_id": "999221",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created_count"] == 1
    items = client.get(f"/api/v1/acquisitions/{acq_id}/items", headers=auth_headers(token)).json()
    assert items["total"] == 1
    row = items["items"][0]
    assert row["is_placeholder"] is True
    assert row["is_tree_linked"] is True
    assert row["issue_number"] == "221"
    assert row["publisher"] == "Marvel"
    assert "Uncanny X-Men" in (row["series"] or "")


def test_create_placeholder_from_unknown_issue(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "tree2@test.com")
    _seed_volume(session)
    acq_id = _create_acq(client, token)
    resp = client.post(
        f"/api/v1/acquisitions/{acq_id}/placeholder-items/tree/unknown",
        headers=auth_headers(token),
        json={"publisher": "Marvel", "volume_id": 12345, "quantity": 2},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created_count"] == 2
    items = client.get(f"/api/v1/acquisitions/{acq_id}/items", headers=auth_headers(token)).json()
    assert items["total"] == 2
    assert items["items"][0]["issue_number"] in ("", None)


def test_create_placeholder_range_and_preview(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "tree3@test.com")
    _seed_volume(session)
    acq_id = _create_acq(client, token)
    client.post(
        f"/api/v1/acquisitions/{acq_id}/placeholder-items/tree",
        headers=auth_headers(token),
        json={"publisher": "Marvel", "volume_id": 12345, "issue_number": "187", "quantity": 1},
    )
    preview = client.post(
        f"/api/v1/acquisitions/{acq_id}/placeholder-items/tree/range/preview",
        headers=auth_headers(token),
        json={"publisher": "Marvel", "volume_id": 12345, "start_issue": 186, "end_issue": 188},
    )
    assert preview.status_code == 200, preview.text
    prev = preview.json()
    assert prev["will_create"] == 2
    assert prev["skipped_existing"] == 1

    created = client.post(
        f"/api/v1/acquisitions/{acq_id}/placeholder-items/tree/range",
        headers=auth_headers(token),
        json={"publisher": "Marvel", "volume_id": 12345, "start_issue": 186, "end_issue": 188},
    )
    assert created.status_code == 200, created.text
    assert created.json()["created_count"] == 2


def test_tree_placeholder_duplicate_prevention(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "tree4@test.com")
    _seed_volume(session)
    acq_id = _create_acq(client, token)
    payload = {"publisher": "Marvel", "volume_id": 12345, "issue_number": "221", "quantity": 1}
    first = client.post(
        f"/api/v1/acquisitions/{acq_id}/placeholder-items/tree",
        headers=auth_headers(token),
        json=payload,
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/v1/acquisitions/{acq_id}/placeholder-items/tree",
        headers=auth_headers(token),
        json=payload,
    )
    assert second.status_code == 200
    assert second.json()["created_count"] == 0
    assert second.json()["skipped_count"] == 1


def test_tree_placeholder_no_comicvine_api(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "tree5@test.com")
    _seed_volume(session)
    acq_id = _create_acq(client, token)
    with patch("httpx.request") as mocked:
        mocked.side_effect = AssertionError("ComicVine HTTP must not be called")
        paths = [
            (
                "POST",
                f"/api/v1/acquisitions/{acq_id}/placeholder-items/tree",
                {"publisher": "Marvel", "volume_id": 12345, "issue_number": "221", "quantity": 1},
            ),
            (
                "POST",
                f"/api/v1/acquisitions/{acq_id}/placeholder-items/tree/unknown",
                {"publisher": "Marvel", "volume_id": 12345, "quantity": 1},
            ),
            (
                "POST",
                f"/api/v1/acquisitions/{acq_id}/placeholder-items/tree/range/preview",
                {"publisher": "Marvel", "volume_id": 12345, "start_issue": 1, "end_issue": 3},
            ),
        ]
        for method, path, body in paths:
            resp = client.request(method, path, headers=auth_headers(token), json=body)
            assert resp.status_code == 200, resp.text
