from fastapi.testclient import TestClient

from app.services.metadata_enrichment import RELEASE_DATE_REVIEW_NOTE


def register_and_login(client: TestClient, email: str = "releases@example.com") -> str:
    client.post(
        "/auth/register",
        json={"email": email, "password": "supersecret123"},
    )
    response = client.post(
        "/auth/login",
        json={"email": email, "password": "supersecret123"},
    )
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_clean_manual_payload(import_id_stub: str) -> dict:
    return {
        "raw_text": f"notes {import_id_stub}",
        "retailer": "Midtown",
        "order_date": "2026-05-21",
        "source_type": "manual_draft",
        "shipping_amount": "0.00",
        "tax_amount": "0.00",
        "items": [
            {
                "publisher": "Marvel",
                "title": "Spider-Man Annual",
                "issue_number": "1",
                "cover_name": None,
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": "4.99",
            }
        ],
        "warnings": [],
        "confidence_score": 1.0,
    }


def test_release_date_review_fields_and_filters_on_imports(client: TestClient) -> None:
    token = register_and_login(client, email="release-filter@example.com")

    malformed = client.post(
        "/imports/manual",
        json={
            "raw_text": "bad date line item",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "items": [
                {
                    "publisher": "Image",
                    "title": "Saga",
                    "release_date": "05/2024",
                    "issue_number": "1",
                    "cover_name": None,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": "3.49",
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        },
        headers=auth_headers(token),
    )
    assert malformed.status_code == 201
    bad_body = malformed.json()
    bad_id = bad_body["id"]
    assert bad_body["needs_release_date_review"] is True
    assert bad_body["release_date_review_item_count"] == 1
    bad_notes_list = bad_body["parsed_payload_json"]["items"][0]["metadata_review_notes"]
    assert RELEASE_DATE_REVIEW_NOTE in bad_notes_list

    clean_a = client.post(
        "/imports/manual",
        json=build_clean_manual_payload("a"),
        headers=auth_headers(token),
    )
    assert clean_a.status_code == 201
    assert clean_a.json()["needs_release_date_review"] is False

    clean_b = client.post(
        "/imports/manual",
        json={
            **build_clean_manual_payload("b"),
            "items": [
                {
                    **build_clean_manual_payload("b")["items"][0],
                    "release_date": "2026-06-01",
                }
            ],
        },
        headers=auth_headers(token),
    )
    assert clean_b.status_code == 201
    assert clean_b.json()["needs_release_date_review"] is False

    flagged = client.get(
        "/imports?needs_release_date_review=true",
        headers=auth_headers(token),
    )
    assert flagged.status_code == 200
    assert flagged.json()["total"] == 1
    assert flagged.json()["items"][0]["id"] == bad_id


def test_confirm_import_with_malformed_release_date_still_succeeds(
    client: TestClient,
) -> None:
    token = register_and_login(client, email="release-confirm@example.com")
    created = client.post(
        "/imports/manual",
        json={
            "raw_text": "confirm path",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "items": [
                {
                    "publisher": "Image",
                    "title": "Saga",
                    "release_date": "not-a-real-date",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": "9.99",
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        },
        headers=auth_headers(token),
    )
    assert created.status_code == 201
    assert created.json()["needs_release_date_review"] is True

    confirm = client.post(
        f"/imports/{created.json()['id']}/confirm",
        headers=auth_headers(token),
    )
    assert confirm.status_code == 200
    assert confirm.json()["total_items"] == 1

