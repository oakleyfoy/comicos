from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import CanonicalSeries, InventoryCopy, MetadataAlias
from app.services.canonical_series import compute_series_key, get_or_create_canonical_series
from app.services.inventory import find_duplicate_inventory_candidates


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_order_payload(
    *,
    publisher: str = "Image",
    title: str = "Invincible",
    quantity: int = 1,
    release_date: str | None = None,
) -> dict:
    return {
        "retailer": "Whatnot",
        "order_date": "2026-05-19",
        "source_type": "manual",
        "shipping_amount": 0.00,
        "tax_amount": 0.00,
        "items": [
            {
                "title": title,
                "publisher": publisher,
                "release_date": release_date,
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": quantity,
                "raw_item_price": 7.65,
            }
        ],
    }


def build_manual_import_payload(
    *,
    publisher: str = "Image",
    title: str = "Invincible",
    release_date: str | None = None,
) -> dict:
    return {
        "raw_text": f"{publisher} {title} order",
        "retailer": "Midtown",
        "order_date": "2026-05-21",
        "source_type": "manual_draft",
        "shipping_amount": "0.00",
        "tax_amount": "0.00",
        "items": [
            {
                "publisher": publisher,
                "title": title,
                "release_date": release_date,
                "issue_number": "1",
                "cover_name": "Cover A",
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


def test_same_publisher_title_resolves_same_canonical_series(
    client: TestClient,
    session: Session,
) -> None:
    del client
    first = get_or_create_canonical_series(
        session,
        publisher="Image",
        canonical_title="Invincible",
    )
    second = get_or_create_canonical_series(
        session,
        publisher="Image",
        canonical_title="Invincible",
    )

    assert first.id == second.id
    assert first.series_key == compute_series_key("Image", "Invincible")


def test_different_publishers_same_title_create_different_canonical_series(
    client: TestClient,
    session: Session,
) -> None:
    del client
    image_series = get_or_create_canonical_series(
        session,
        publisher="Image",
        canonical_title="Frontier",
    )
    dc_series = get_or_create_canonical_series(
        session,
        publisher="DC",
        canonical_title="Frontier",
    )

    assert image_series.id != dc_series.id
    assert image_series.series_key != dc_series.series_key


def test_alias_normalized_series_maps_to_same_canonical_series(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "alias-series@example.com")
    session.add(
        MetadataAlias(
            alias_type="series",
            alias_value="Ultimate Spider-man",
            canonical_value="Ultimate Spider-Man",
            source="manual",
            is_active=True,
        )
    )
    session.commit()

    first = client.post(
        "/orders",
        json=build_order_payload(
            publisher="Marvel",
            title="Ultimate Spider-man",
            quantity=1,
        ),
        headers=auth_headers(token),
    )
    second = client.post(
        "/orders",
        json=build_order_payload(
            publisher="Marvel",
            title="Ultimate Spider-Man",
            quantity=1,
        ),
        headers=auth_headers(token),
    )

    assert first.status_code == 201
    assert second.status_code == 201

    canonical_series = session.exec(select(CanonicalSeries)).all()
    assert len(canonical_series) == 1
    assert canonical_series[0].canonical_publisher == "Marvel"
    assert canonical_series[0].canonical_title == "Ultimate Spider-Man"


def test_confirm_import_stores_canonical_series_id(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "confirm-series@example.com")
    create_response = client.post(
        "/imports/manual",
        json=build_manual_import_payload(
            publisher="Image",
            title="Saga",
            release_date="2024-05-17",
        ),
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201

    confirm_response = client.post(
        f"/imports/{create_response.json()['id']}/confirm",
        headers=auth_headers(token),
    )
    assert confirm_response.status_code == 200

    copies = session.exec(select(InventoryCopy)).all()
    assert len(copies) == 1
    assert copies[0].canonical_series_id is not None

    canonical_series = session.get(CanonicalSeries, copies[0].canonical_series_id)
    assert canonical_series is not None
    assert canonical_series.canonical_publisher == "Image"
    assert canonical_series.canonical_title == "Saga"
    assert copies[0].release_date == date(2024, 5, 17)
    assert copies[0].release_year == 2024
    assert canonical_series.earliest_known_release_date == date(2024, 5, 17)
    assert canonical_series.latest_known_release_date == date(2024, 5, 17)


def test_ops_canonical_series_endpoint_returns_filtered_inventory_counts(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-series@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops-series@example.com")

    assert (
        client.post(
            "/orders",
            json=build_order_payload(
                publisher="Image",
                title="Invincible",
                quantity=2,
                release_date="2024-05-17",
            ),
            headers=auth_headers(token),
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/orders",
            json=build_order_payload(publisher="DC", title="Batman", quantity=1),
            headers=auth_headers(token),
        ).status_code
        == 201
    )

    response = client.get(
        "/ops/canonical-series",
        headers=auth_headers(token),
        params={"publisher": "Image", "title": "Invincible"},
    )

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["canonical_publisher"] == "Image"
    assert rows[0]["canonical_title"] == "Invincible"
    assert rows[0]["series_key"] == "Image|Invincible"
    assert rows[0]["inventory_count"] == 2
    assert rows[0]["earliest_known_release_date"] == "2024-05-17"
    assert rows[0]["latest_known_release_date"] == "2024-05-17"
    assert rows[0]["is_active"] is True

    narrowed = client.get(
        "/ops/canonical-series",
        headers=auth_headers(token),
        params={
            "earliest_release_year_min": 2024,
            "earliest_release_year_max": 2024,
            "publisher": "Image",
        },
    )
    assert narrowed.status_code == 200
    assert len(narrowed.json()) == 1
    empty = client.get(
        "/ops/canonical-series",
        headers=auth_headers(token),
        params={
            "earliest_release_year_min": 2099,
        },
    )
    assert empty.status_code == 200
    assert empty.json() == []


def test_duplicate_candidate_logic_still_works_with_canonical_series_links(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "duplicate-series@example.com")
    response = client.post(
        "/orders",
        json=build_order_payload(publisher="Image", title="Monstress", quantity=2),
        headers=auth_headers(token),
    )
    assert response.status_code == 201

    copies = session.exec(select(InventoryCopy).order_by(InventoryCopy.id.asc())).all()
    assert len(copies) == 2
    assert all(copy.canonical_series_id is not None for copy in copies)

    duplicates = find_duplicate_inventory_candidates(session)
    assert len(duplicates) == 1
    assert duplicates[0].metadata_identity_key == "Image|Monstress|1|Cover A"
