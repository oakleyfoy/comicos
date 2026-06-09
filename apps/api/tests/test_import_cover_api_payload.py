from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogVariant
from tests.test_imports import auth_headers, register_and_login


def test_get_import_includes_cover_url_in_payload(client: TestClient, session: Session) -> None:
    issue = ExternalCatalogIssue(
        source_name="locg",
        title="Nova #4",
        publisher="Marvel",
        series_name="Nova",
        issue_number="4",
        release_date=date(2026, 7, 22),
        cover_image_url="https://example.com/nova-issue.jpg",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    assert issue.id is not None

    variant = ExternalCatalogVariant(
        external_issue_id=issue.id,
        cover_label="Cover A",
        image_url="https://example.com/nova-a.jpg",
    )
    session.add(variant)
    session.commit()

    token = register_and_login(client)
    create_response = client.post(
        "/imports/manual",
        json={
            "retailer": "Midtown",
            "order_date": "2026-06-01",
            "source_type": "manual_draft",
            "items": [
                {
                    "publisher": "Marvel",
                    "title": "Nova",
                    "issue_number": "4",
                    "cover_name": "Cover A",
                    "quantity": 1,
                    "raw_item_price": "3.99",
                    "catalog_match_source": "ExternalCatalogIssue",
                    "catalog_match_source_id": issue.id,
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        },
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201
    import_id = create_response.json()["id"]

    get_response = client.get(f"/imports/{import_id}", headers=auth_headers(token))
    assert get_response.status_code == 200
    item = get_response.json()["parsed_payload_json"]["items"][0]
    assert item["cover_image_url"] == "https://example.com/nova-a.jpg"
    assert item["cover_url"] == "https://example.com/nova-a.jpg"
    assert item["has_cover_image"] is True
