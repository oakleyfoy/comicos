from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.acquisition import Acquisition, AcquisitionPlaceholderIssue, CATALOG_STATUS_PLACEHOLDER
from app.models.asset_ledger import InventoryCopy
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.catalog_p97 import ComicVineVolumeUniverse
from test_inventory import auth_headers, register_and_login


def _seed_gap_world(session: Session) -> dict:
    publisher = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(publisher)
    session.flush()
    series = CatalogSeries(
        publisher_id=publisher.id,
        name="Amazing Spider-Man",
        normalized_name="amazing spider man",
        start_year=2018,
        external_source_ids={"COMICVINE": {"99999": True}},
    )
    session.add(series)
    session.flush()
    issue_owned = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(publisher.id),
        issue_number="1",
        normalized_issue_number="1",
        title="Owned",
        release_date=date(2025, 1, 15),
    )
    issue_missing = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(publisher.id),
        issue_number="2",
        normalized_issue_number="2",
        title="Missing",
        release_date=date(2025, 2, 1),
    )
    issue_sold = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(publisher.id),
        issue_number="3",
        normalized_issue_number="3",
        title="Sold",
        release_date=date(2025, 3, 1),
    )
    issue_2024 = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(publisher.id),
        issue_number="4",
        normalized_issue_number="4",
        title="Older",
        release_date=date(2024, 12, 1),
    )
    issue_ph = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(publisher.id),
        issue_number="5",
        normalized_issue_number="5",
        title="Placeholder slot",
        release_date=date(2025, 5, 1),
    )
    indie_pub = CatalogPublisher(name="Indie Co", normalized_name="indie co")
    session.add(indie_pub)
    session.flush()
    indie_series = CatalogSeries(
        publisher_id=indie_pub.id,
        name="Indie Book",
        normalized_name="indie book",
        start_year=2025,
    )
    session.add(indie_series)
    session.flush()
    session.add(
        CatalogIssue(
            series_id=int(indie_series.id),
            publisher_id=int(indie_pub.id),
            issue_number="1",
            normalized_issue_number="1",
            release_date=date(2025, 4, 1),
        )
    )
    session.add_all([issue_owned, issue_missing, issue_sold, issue_2024, issue_ph])
    session.flush()
    session.add(
        ComicVineVolumeUniverse(
            volume_id=99999,
            name="Amazing Spider-Man",
            publisher="Marvel",
            start_year=2018,
            count_of_issues=100,
        )
    )
    session.commit()
    return {
        "volume_id": 99999,
        "series_id": int(series.id),
        "publisher_id": int(publisher.id),
        "issue_owned_id": int(issue_owned.id or 0),
        "issue_missing_id": int(issue_missing.id or 0),
        "issue_sold_id": int(issue_sold.id or 0),
    }


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _seed_user_inventory(session: Session, user_id: int, meta: dict) -> None:
    acq = Acquisition(
        user_id=user_id,
        acquisition_type="FACEBOOK",
        seller_name="Test",
        total_paid=Decimal("10.00"),
        shipping_paid=Decimal("0"),
        tax_paid=Decimal("0"),
        status="OPEN",
    )
    session.add(acq)
    session.flush()
    session.add(
        InventoryCopy(
            user_id=user_id,
            acquisition_id=int(acq.id or 0),
            catalog_issue_id=meta["issue_owned_id"],
            copy_number=1,
            acquisition_cost=Decimal("5.00"),
            variant_status="RESOLVED",
            hold_status="hold",
        )
    )
    session.add(
        InventoryCopy(
            user_id=user_id,
            acquisition_id=int(acq.id or 0),
            catalog_issue_id=meta["issue_sold_id"],
            copy_number=1,
            acquisition_cost=Decimal("5.00"),
            variant_status="RESOLVED",
            hold_status="sold",
        )
    )
    ph = AcquisitionPlaceholderIssue(
        acquisition_id=int(acq.id or 0),
        user_id=user_id,
        title="Amazing Spider-Man",
        issue_number="5",
        publisher="Marvel",
        quantity=1,
        catalog_status=CATALOG_STATUS_PLACEHOLDER,
        source_volume_id=meta["volume_id"],
        tree_linked=True,
    )
    session.add(ph)
    session.flush()
    session.add(
        InventoryCopy(
            user_id=user_id,
            acquisition_id=int(acq.id or 0),
            placeholder_issue_id=int(ph.id or 0),
            copy_number=1,
            acquisition_cost=Decimal("3.00"),
            variant_status="PLACEHOLDER",
            hold_status="hold",
        )
    )
    session.commit()


def test_years_descending_from_2025(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "gap-years@test.com")
    _seed_gap_world(session)
    resp = client.get("/api/v1/collection-gaps/years", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["default_year"] == 2025
    years = [row["year"] for row in body["items"]]
    assert years[0] == 2025
    assert years == sorted(years, reverse=True)


def test_publisher_priority_sort(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "gap-pub@test.com")
    _seed_gap_world(session)
    resp = client.get("/api/v1/collection-gaps/years/2025/publishers", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    pubs = [row["publisher"] for row in resp.json()["items"]]
    assert pubs[0] == "Marvel"


def test_volume_completion_counts(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "gap-vol@test.com")
    meta = _seed_gap_world(session)
    _seed_user_inventory(session, _owner_id(session, "gap-vol@test.com"), meta)
    resp = client.get(
        "/api/v1/collection-gaps/publishers/Marvel/volumes?year=2025",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    row = next(item for item in resp.json()["items"] if item["volume_id"] == meta["volume_id"])
    assert row["issue_count_in_year"] >= 4
    assert row["owned_count"] >= 2
    assert row["missing_count"] >= 1


def test_issue_gap_statuses(client: TestClient, session: Session) -> None:
    email = "gap-issues@test.com"
    token = register_and_login(client, email)
    meta = _seed_gap_world(session)
    _seed_user_inventory(session, _owner_id(session, email), meta)
    resp = client.get(
        f"/api/v1/collection-gaps/volumes/{meta['volume_id']}/issues?year=2025",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    by_num = {row["issue_number"]: row["gap_status"] for row in resp.json()["items"]}
    assert by_num["1"] == "OWNED"
    assert by_num["2"] == "MISSING"
    assert by_num["3"] == "SOLD_HISTORY"
    assert by_num["5"] == "PLACEHOLDER_OWNED"


def test_wantlist_targets_and_duplicate_prevention(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "gap-want@test.com")
    meta = _seed_gap_world(session)
    payload = {
        "targets": [
            {
                "publisher": "Marvel",
                "series_title": "Amazing Spider-Man",
                "volume_id": meta["volume_id"],
                "issue_number": "2",
                "catalog_issue_id": meta["issue_missing_id"],
            }
        ]
    }
    first = client.post("/api/v1/collection-gaps/wantlist-targets", headers=auth_headers(token), json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["created_count"] == 1
    second = client.post("/api/v1/collection-gaps/wantlist-targets", headers=auth_headers(token), json=payload)
    assert second.json()["created_count"] == 0
    assert second.json()["skipped_duplicates"] == 1


def test_no_comicvine_api(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "gap-cv@test.com")
    meta = _seed_gap_world(session)
    with patch("httpx.request") as mocked:
        mocked.side_effect = AssertionError("ComicVine HTTP must not be called")
        assert client.get("/api/v1/collection-gaps/years", headers=auth_headers(token)).status_code == 200
        assert (
            client.get("/api/v1/collection-gaps/years/2025/publishers", headers=auth_headers(token)).status_code == 200
        )
        assert (
            client.get(
                "/api/v1/collection-gaps/publishers/Marvel/volumes?year=2025",
                headers=auth_headers(token),
            ).status_code
            == 200
        )
        assert (
            client.get(
                f"/api/v1/collection-gaps/volumes/{meta['volume_id']}/issues?year=2025",
                headers=auth_headers(token),
            ).status_code
            == 200
        )
