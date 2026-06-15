from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.catalog_master import CatalogImage, CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.catalog_ingestion_service import normalize_issue_number
from test_inventory import auth_headers, register_and_login


def _seed_venom_catalog(session: Session, *, count: int = 8) -> dict[str, int]:
    publisher = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(publisher)
    session.flush()
    series = CatalogSeries(
        name="Venom",
        normalized_name="venom",
        publisher_id=publisher.id,
        start_year=2003,
        volume_number=1,
    )
    session.add(series)
    session.flush()
    issue_ids: dict[str, int] = {}
    for number in range(1, count + 1):
        issue = CatalogIssue(
            series_id=series.id,
            publisher_id=publisher.id,
            issue_number=str(number),
            normalized_issue_number=normalize_issue_number(str(number)),
            title="Rex, Part 1" if number == 1 else None,
            cover_date=date(2003, 4, 1) if number == 1 else None,
        )
        session.add(issue)
        session.flush()
        session.add(
            CatalogImage(
                issue_id=issue.id,
                image_type="cover",
                source_url=f"https://example.com/venom-{number}.jpg",
                source="comicvine",
            )
        )
        issue_ids[str(number)] = int(issue.id)
    session.commit()
    return issue_ids


def test_search_venom_1_returns_catalog_issue(client: TestClient, session: Session) -> None:
    issue_ids = _seed_venom_catalog(session)
    token = register_and_login(client, "candidates-search@example.com")

    response = client.get(
        "/api/v1/recognition/catalog-candidates",
        headers=auth_headers(token),
        params={"q": "Venom 1 Marvel"},
    )
    assert response.status_code == 200, response.text
    cards = response.json()
    assert cards, "expected at least one candidate"
    top = cards[0]
    assert top["catalog_issue_id"] == issue_ids["1"]
    assert top["series"] == "Venom"
    assert top["issue_number"] == "1"
    assert top["publisher"] == "Marvel"
    assert top["cover_image_url"] == "https://example.com/venom-1.jpg"
    assert top["series_start_year"] == 2003
    assert top["issue_title"] == "Rex, Part 1"


def test_search_ranks_exact_series_before_spinoff(client: TestClient, session: Session) -> None:
    publisher = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(publisher)
    session.flush()
    core = CatalogSeries(name="Venom", normalized_name="venom", publisher_id=publisher.id, start_year=2003)
    spinoff = CatalogSeries(
        name="Venom: Lethal Protector",
        normalized_name="venom lethal protector",
        publisher_id=publisher.id,
        start_year=1993,
    )
    session.add(core)
    session.add(spinoff)
    session.flush()
    for ser in (core, spinoff):
        issue = CatalogIssue(
            series_id=ser.id,
            publisher_id=publisher.id,
            issue_number="1",
            normalized_issue_number="1",
        )
        session.add(issue)
        session.flush()
        session.add(
            CatalogImage(
                issue_id=issue.id,
                image_type="cover",
                source_url=f"https://example.com/{ser.id}-1.jpg",
                source="test",
            )
        )
    session.commit()

    token = register_and_login(client, "candidates-rank@example.com")
    response = client.get(
        "/api/v1/recognition/catalog-candidates",
        headers=auth_headers(token),
        params={"q": "Venom 1"},
    )
    assert response.status_code == 200, response.text
    cards = response.json()
    assert cards[0]["series"] == "Venom"
    assert cards[0]["series_start_year"] == 2003


def test_nearby_issues_returns_same_series_candidates(client: TestClient, session: Session) -> None:
    issue_ids = _seed_venom_catalog(session)
    token = register_and_login(client, "candidates-nearby@example.com")

    response = client.get(
        "/api/v1/recognition/catalog-candidates",
        headers=auth_headers(token),
        params={"catalog_issue_id": issue_ids["7"]},
    )
    assert response.status_code == 200, response.text
    cards = response.json()
    assert len(cards) > 1
    assert all(card["series"] == "Venom" for card in cards)
    numbers = {card["issue_number"] for card in cards}
    assert "7" in numbers
    assert "8" in numbers
    # #1 is more than the 5-issue window away from #7 and must be excluded.
    assert "1" not in numbers


def test_search_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/recognition/catalog-candidates", params={"q": "Venom"})
    assert response.status_code == 401
