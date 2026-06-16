from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.catalog_p97 import ComicVineVolumeUniverse
from test_inventory import auth_headers, register_and_login


def _seed(client: TestClient, session: Session, email: str = "universe@test.com") -> str:
    token = register_and_login(client, email)
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
    session.add(
        CatalogIssue(
            series_id=int(series.id),
            publisher_id=int(publisher.id),
            issue_number="221",
            normalized_issue_number="221",
            title="Fall of the Mutants",
            external_source_ids={"COMICVINE": {"999221": True}},
        )
    )
    session.add(
        ComicVineVolumeUniverse(
            volume_id=12345,
            name="Uncanny X-Men",
            publisher="Marvel",
            start_year=1981,
            count_of_issues=500,
        )
    )
    session.add(
        ComicVineVolumeUniverse(
            volume_id=54321,
            name="Action Comics",
            publisher="DC Comics",
            start_year=1938,
            count_of_issues=1000,
        )
    )
    session.commit()
    return token


def test_publishers_endpoint_returns_grouped_publishers(client: TestClient, session: Session) -> None:
    token = _seed(client, session)
    resp = client.get("/api/v1/catalog-universe/publishers", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"]["total_publishers"] >= 2
    names = {row["publisher"] for row in body["items"]}
    assert "Marvel" in names
    assert "DC Comics" in names
    marvel = next(row for row in body["items"] if row["publisher"] == "Marvel")
    assert marvel["volume_count"] >= 1
    assert marvel["issue_count"] >= 1


def test_publisher_volumes_endpoint_returns_volumes(client: TestClient, session: Session) -> None:
    token = _seed(client, session)
    resp = client.get(
        "/api/v1/catalog-universe/publishers/Marvel/volumes",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["publisher"] == "Marvel"
    assert any(row["volume_id"] == 12345 for row in body["items"])
    volume = next(row for row in body["items"] if row["volume_id"] == 12345)
    assert volume["catalog_issue_count"] == 1
    assert volume["missing_issue_count"] == 499


def test_volume_issues_endpoint_returns_issues(client: TestClient, session: Session) -> None:
    token = _seed(client, session)
    resp = client.get(
        "/api/v1/catalog-universe/volumes/12345/issues",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_count"] == 1
    assert body["items"][0]["issue_number"] == "221"
    assert body["items"][0]["normalized_issue_number"] == "221"
    assert body["items"][0]["catalog_status"] == "CATALOGED"
    assert body["items"][0]["catalog_issue_id"] is not None
    assert body["items"][0]["has_variants"] is False
    assert body["items"][0]["cover_count"] == 1


def test_volume_issue_variants_endpoint(client: TestClient, session: Session) -> None:
    token = _seed(client, session)
    resp = client.get(
        "/api/v1/catalog-universe/volumes/12345/issues/221/variants",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["issue_number"] == "221"
    assert len(body["options"]) >= 1
    assert body["options"][0]["catalog_issue_id"] is not None


def test_search_endpoint_finds_series_by_title(client: TestClient, session: Session) -> None:
    token = _seed(client, session)
    resp = client.get(
        "/api/v1/catalog-universe/search?q=Uncanny",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_count"] >= 1
    assert any(hit["hit_type"] == "volume" for hit in body["hits"])


def test_no_comicvine_api_call_is_made(client: TestClient, session: Session) -> None:
    token = _seed(client, session)
    with patch("httpx.request") as mocked:
        mocked.side_effect = AssertionError("ComicVine HTTP must not be called")
        endpoints = [
            "/api/v1/catalog-universe/publishers",
            "/api/v1/catalog-universe/publishers/Marvel/volumes",
            "/api/v1/catalog-universe/volumes/12345/issues",
            "/api/v1/catalog-universe/search?q=X-Men",
        ]
        for path in endpoints:
            resp = client.get(path, headers=auth_headers(token))
            assert resp.status_code == 200, resp.text
