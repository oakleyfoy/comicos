from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.catalog_p97 import P97ComicVineVolumeQueue


def _seed_queue(session: Session) -> None:
    session.add(
        P97ComicVineVolumeQueue(
            comicvine_volume_id=9001,
            status="imported",
            series_name="Fantastic Four",
            publisher="Marvel",
            issues_created=416,
            issues_updated=12,
            api_requests_used=50,
        )
    )
    session.add(
        P97ComicVineVolumeQueue(
            comicvine_volume_id=9002,
            status="pending",
            series_name="Next Volume",
            publisher="Marvel",
        )
    )
    session.commit()


def test_volume_analytics_api_endpoints(client: TestClient, session: Session) -> None:
    _seed_queue(session)

    summary = client.get("/p97/volume-analytics/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["imported_volumes"] == 1
    assert body["pending_volumes"] == 1
    assert body["issues_created"] == 416

    top_created = client.get("/p97/volume-analytics/top-created?limit=5")
    assert top_created.status_code == 200
    created = top_created.json()
    assert len(created) == 1
    assert created[0]["volume_id"] == 9001
    assert created[0]["issues_created"] == 416

    top_updated = client.get("/p97/volume-analytics/top-updated?limit=5")
    assert top_updated.status_code == 200
    assert top_updated.json()[0]["issues_updated"] == 12

    publishers = client.get("/p97/volume-analytics/publishers")
    assert publishers.status_code == 200
    assert publishers.json()[0]["publisher"] == "Marvel"

    forecast = client.get("/p97/volume-analytics/remaining-forecast")
    assert forecast.status_code == 200
    assert len(forecast.json()) == 1

    projection = client.get("/p97/volume-analytics/final-projection")
    assert projection.status_code == 200
    proj = projection.json()
    assert "current_catalog_size" in proj
    assert "projected_final_catalog_size" in proj
