from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
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


def _seed_universe_with_catalog(session: Session) -> None:
    publisher = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(publisher)
    session.flush()
    series = CatalogSeries(
        publisher_id=publisher.id,
        name="Uncanny X-Men",
        normalized_name="uncanny x men",
        start_year=1963,
        external_source_ids={"COMICVINE": {"12345": True}},
    )
    session.add(series)
    session.flush()
    session.add(
        CatalogIssue(
            series_id=int(series.id),
            publisher_id=int(publisher.id),
            issue_number="186",
            normalized_issue_number="186",
            title="Legacy",
        )
    )
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


def test_range_preview_honors_excludes(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "range-prev@test.com")
    _seed_universe_with_catalog(session)
    acq_id = _create_acq(client, token)
    resp = client.post(
        f"/api/v1/acquisitions/{acq_id}/placeholder-items/range-preview",
        headers=auth_headers(token),
        json={
            "publisher": "Marvel",
            "volume_id": 12345,
            "start_issue": 186,
            "end_issue": 188,
            "exclude_issues": ["187"],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_issues_in_range"] == 3
    assert body["excluded_count"] == 1
    assert body["catalog_items_to_add"] == 1
    assert body["placeholders_to_create"] == 1
    assert "187" not in body["placeholder_issue_numbers"]


def test_range_create_mixed_catalog_and_placeholder(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "range-create@test.com")
    _seed_universe_with_catalog(session)
    acq_id = _create_acq(client, token)
    resp = client.post(
        f"/api/v1/acquisitions/{acq_id}/placeholder-items/range-create",
        headers=auth_headers(token),
        json={
            "publisher": "Marvel",
            "volume_id": 12345,
            "start_issue": 186,
            "end_issue": 187,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["catalog_created"] == 1
    assert body["placeholder_created"] == 1
    items = client.get(f"/api/v1/acquisitions/{acq_id}/items", headers=auth_headers(token)).json()
    assert items["total"] == 2


def test_range_duplicate_prevention(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "range-dup@test.com")
    _seed_universe_with_catalog(session)
    acq_id = _create_acq(client, token)
    client.post(
        f"/api/v1/acquisitions/{acq_id}/placeholder-items/tree",
        headers=auth_headers(token),
        json={"publisher": "Marvel", "volume_id": 12345, "issue_number": "187", "quantity": 1},
    )
    preview = client.post(
        f"/api/v1/acquisitions/{acq_id}/placeholder-items/range-preview",
        headers=auth_headers(token),
        json={
            "publisher": "Marvel",
            "volume_id": 12345,
            "start_issue": 186,
            "end_issue": 188,
        },
    ).json()
    assert preview["skipped_duplicates"] >= 1


def test_range_create_with_variant_label(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "range-var@test.com")
    _seed_universe_with_catalog(session)
    acq_id = _create_acq(client, token)
    client.post(
        f"/api/v1/acquisitions/{acq_id}/placeholder-items/range-create",
        headers=auth_headers(token),
        json={
            "publisher": "Marvel",
            "volume_id": 12345,
            "start_issue": 187,
            "end_issue": 187,
            "variant_label": "Newsstand",
            "cover_type": "Newsstand",
            "raw_variant_notes": "Newsstand barcode",
        },
    )
    items = client.get(f"/api/v1/acquisitions/{acq_id}/items", headers=auth_headers(token)).json()
    assert items["items"][0]["variant_label"] == "Newsstand"


def test_range_endpoints_no_comicvine(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "range-cv@test.com")
    _seed_universe_with_catalog(session)
    acq_id = _create_acq(client, token)
    with patch("httpx.request") as mocked:
        mocked.side_effect = AssertionError("ComicVine HTTP must not be called")
        for path in ("range-preview", "range-create"):
            resp = client.post(
                f"/api/v1/acquisitions/{acq_id}/placeholder-items/{path}",
                headers=auth_headers(token),
                json={
                    "publisher": "Marvel",
                    "volume_id": 12345,
                    "start_issue": 187,
                    "end_issue": 187,
                },
            )
            assert resp.status_code == 200, resp.text
