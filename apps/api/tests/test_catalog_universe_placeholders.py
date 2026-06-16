from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.catalog_p97 import ComicVineVolumeUniverse
from test_inventory import auth_headers, register_and_login


def _seed(client: TestClient, session: Session) -> tuple[str, int, int]:
    token = register_and_login(client, "ph-queue@test.com")
    publisher = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(publisher)
    session.flush()
    series = CatalogSeries(
        publisher_id=publisher.id,
        name="Uncanny X-Men",
        normalized_name="uncanny x men",
        start_year=1981,
        external_source_ids={"COMICVINE": {"12345": True}},
    )
    session.add(series)
    session.flush()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(publisher.id),
        issue_number="221",
        normalized_issue_number="221",
        title="Fall of the Mutants",
    )
    session.add(issue)
    session.flush()
    session.add(
        ComicVineVolumeUniverse(
            volume_id=12345,
            name="Uncanny X-Men",
            publisher="Marvel",
            start_year=1981,
            count_of_issues=500,
        )
    )
    session.commit()
    acq = client.post(
        "/api/v1/acquisitions",
        headers=auth_headers(token),
        json={
            "acquisition_type": "FACEBOOK",
            "purchase_date": "2026-06-01",
            "seller_name": "Lot",
            "total_paid": "100.00",
            "shipping_paid": "0.00",
            "tax_paid": "0.00",
        },
    ).json()
    acq_id = int(acq["id"])
    tree = client.post(
        f"/api/v1/acquisitions/{acq_id}/placeholder-items/tree",
        headers=auth_headers(token),
        json={"publisher": "Marvel", "volume_id": 12345, "issue_number": "221", "quantity": 1},
    )
    assert tree.status_code == 200, tree.text
    items = client.get(f"/api/v1/acquisitions/{acq_id}/items", headers=auth_headers(token)).json()
    placeholder_id = int(items["items"][0]["placeholder_issue_id"])
    return token, placeholder_id, int(issue.id or 0)


def test_list_unresolved_placeholders(client: TestClient, session: Session) -> None:
    token, _, _ = _seed(client, session)
    resp = client.get("/api/v1/catalog-universe/placeholders", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_count"] >= 1
    assert body["items"][0]["issue_number"] == "221"


def test_match_candidates_generated(client: TestClient, session: Session) -> None:
    token, placeholder_id, _ = _seed(client, session)
    resp = client.get(
        f"/api/v1/catalog-universe/placeholders/{placeholder_id}/match-candidates",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidates"]
    assert body["candidates"][0]["issue_number"] == "221"
    assert body["candidates"][0]["confidence"] in ("High", "Medium", "Low")


def test_link_preserves_cost_basis(client: TestClient, session: Session) -> None:
    token, placeholder_id, catalog_issue_id = _seed(client, session)
    acq_id = client.get("/api/v1/catalog-universe/placeholders", headers=auth_headers(token)).json()["items"][0][
        "acquisition_id"
    ]
    alloc = client.post(
        f"/api/v1/acquisitions/{acq_id}/allocate",
        headers=auth_headers(token),
        json={"mode": "EVEN"},
    )
    assert alloc.status_code == 200, alloc.text
    copy_id = alloc.json()["items"][0]["inventory_copy_id"]
    cost_before = Decimal(alloc.json()["items"][0]["cost_basis"])

    link = client.post(
        f"/api/v1/catalog-universe/placeholders/{placeholder_id}/link",
        headers=auth_headers(token),
        json={"catalog_issue_id": catalog_issue_id},
    )
    assert link.status_code == 200, link.text
    assert link.json()["inventory_copies_updated"] == 1

    copy = session.exec(select(InventoryCopy).where(InventoryCopy.id == copy_id)).one()
    assert copy.catalog_issue_id == catalog_issue_id
    assert copy.acquisition_cost == cost_before


def test_placeholder_queue_no_comicvine(client: TestClient, session: Session) -> None:
    token, placeholder_id, catalog_issue_id = _seed(client, session)
    with patch("httpx.request") as mocked:
        mocked.side_effect = AssertionError("ComicVine HTTP must not be called")
        assert client.get("/api/v1/catalog-universe/placeholders", headers=auth_headers(token)).status_code == 200
        assert (
            client.get(
                f"/api/v1/catalog-universe/placeholders/{placeholder_id}/match-candidates",
                headers=auth_headers(token),
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/catalog-universe/placeholders/{placeholder_id}/link",
                headers=auth_headers(token),
                json={"catalog_issue_id": catalog_issue_id},
            ).status_code
            == 200
        )
