from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import MetadataAlias
from app.services.metadata_enrichment import (
    normalize_creator_name,
    normalize_publisher_name,
    normalize_series_title_with_aliases,
)


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_manual_import_payload(publisher: str) -> dict:
    return {
        "raw_text": f"{publisher} Babylon Cove #01",
        "retailer": "Midtown",
        "order_date": "2026-05-21",
        "source_type": "manual_draft",
        "shipping_amount": "0.00",
        "tax_amount": "0.00",
        "items": [
            {
                "publisher": publisher,
                "title": "Babylon Cove",
                "issue_number": "01",
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


def build_manual_import_payload_with_series(publisher: str, title: str) -> dict:
    payload = build_manual_import_payload(publisher)
    payload["raw_text"] = f"{publisher} {title} #01"
    payload["items"][0]["title"] = title
    return payload


def test_database_alias_overrides_static_fallback(
    client: TestClient,
    session: Session,
) -> None:
    del client
    session.add(
        MetadataAlias(
            alias_value="Marvel Comics",
            canonical_value="Marvel Legacy",
            alias_type="publisher",
            source="manual",
            is_active=True,
        )
    )
    session.commit()

    normalized = normalize_publisher_name("Marvel Comics", session=session)

    assert normalized.canonical_value == "Marvel Legacy"
    assert normalized.decision == "database_alias"


def test_creating_alias_removes_future_review_flags_for_that_publisher(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops@example.com")

    create_alias = client.post(
        "/ops/metadata-aliases",
        json={
            "alias_value": "Indie House Comics",
            "canonical_value": "Indie House",
            "alias_type": "publisher",
        },
        headers=auth_headers(token),
    )
    assert create_alias.status_code == 201

    import_response = client.post(
        "/imports/manual",
        json=build_manual_import_payload("Indie House Comics"),
        headers=auth_headers(token),
    )

    assert import_response.status_code == 201
    data = import_response.json()
    assert data["needs_metadata_review"] is False
    assert data["parsed_payload_json"]["items"][0]["publisher"] == "Indie House"


def test_inactive_aliases_are_ignored(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops@example.com")

    create_alias = client.post(
        "/ops/metadata-aliases",
        json={
            "alias_value": "Ghost Machine Comics",
            "canonical_value": "Ghost Machine",
            "alias_type": "publisher",
        },
        headers=auth_headers(token),
    )
    assert create_alias.status_code == 201

    deactivate_alias = client.post(
        f"/ops/metadata-aliases/{create_alias.json()['id']}/deactivate",
        headers=auth_headers(token),
    )
    assert deactivate_alias.status_code == 200
    assert deactivate_alias.json()["is_active"] is False

    import_response = client.post(
        "/imports/manual",
        json=build_manual_import_payload("Ghost Machine Comics"),
        headers=auth_headers(token),
    )

    assert import_response.status_code == 201
    data = import_response.json()
    assert data["needs_metadata_review"] is True
    assert data["parsed_payload_json"]["items"][0]["publisher"] == "Ghost Machine Comics"


def test_alias_crud_and_confirm_flow_still_work(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops@example.com")

    create_alias = client.post(
        "/ops/metadata-aliases",
        json={
            "alias_value": "Vault Comics",
            "canonical_value": "Vault",
            "alias_type": "publisher",
        },
        headers=auth_headers(token),
    )
    assert create_alias.status_code == 201

    list_aliases = client.get("/ops/metadata-aliases", headers=auth_headers(token))
    assert list_aliases.status_code == 200
    assert any(alias["alias_value"] == "Vault Comics" for alias in list_aliases.json())

    update_alias = client.patch(
        f"/ops/metadata-aliases/{create_alias.json()['id']}",
        json={"canonical_value": "Vault Comics"},
        headers=auth_headers(token),
    )
    assert update_alias.status_code == 200
    assert update_alias.json()["canonical_value"] == "Vault Comics"

    import_response = client.post(
        "/imports/manual",
        json=build_manual_import_payload("Vault Comics"),
        headers=auth_headers(token),
    )
    assert import_response.status_code == 201
    assert import_response.json()["needs_metadata_review"] is False

    confirm_response = client.post(
        f"/imports/{import_response.json()['id']}/confirm",
        headers=auth_headers(token),
    )
    assert confirm_response.status_code == 200

    aliases = session.exec(select(MetadataAlias)).all()
    assert any(alias.canonical_value == "Vault Comics" for alias in aliases)


def test_series_database_alias_applies_deterministically(
    client: TestClient,
    session: Session,
) -> None:
    del client
    session.add(
        MetadataAlias(
            alias_value="Ultimate Spider-man",
            canonical_value="Ultimate Spider-Man",
            alias_type="series",
            source="manual",
            is_active=True,
        )
    )
    session.commit()

    first = normalize_series_title_with_aliases("Ultimate Spider-man", session=session)
    second = normalize_series_title_with_aliases("Ultimate Spider-man", session=session)

    assert first == second
    assert first.canonical_value == "Ultimate Spider-Man"
    assert first.decision == "database_alias"


def test_inactive_series_aliases_are_ignored(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops@example.com")

    create_alias = client.post(
        "/ops/metadata-aliases",
        json={
            "alias_value": "tmnt",
            "canonical_value": "Teenage Mutant Ninja Turtles",
            "alias_type": "series",
        },
        headers=auth_headers(token),
    )
    assert create_alias.status_code == 201

    deactivate_alias = client.post(
        f"/ops/metadata-aliases/{create_alias.json()['id']}/deactivate",
        headers=auth_headers(token),
    )
    assert deactivate_alias.status_code == 200

    import_response = client.post(
        "/imports/manual",
        json=build_manual_import_payload_with_series("IDW Publishing", "tmnt"),
        headers=auth_headers(token),
    )

    assert import_response.status_code == 201
    item = import_response.json()["parsed_payload_json"]["items"][0]
    assert item["title"] == "Tmnt"


def test_creating_series_alias_updates_future_draft_enrichment(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops@example.com")

    create_alias = client.post(
        "/ops/metadata-aliases",
        json={
            "alias_value": "tmnt",
            "canonical_value": "Teenage Mutant Ninja Turtles",
            "alias_type": "series",
        },
        headers=auth_headers(token),
    )
    assert create_alias.status_code == 201

    series_only = client.get(
        "/ops/metadata-aliases?alias_type=series",
        headers=auth_headers(token),
    )
    assert series_only.status_code == 200
    assert any(alias["alias_type"] == "series" for alias in series_only.json())

    import_response = client.post(
        "/imports/manual",
        json=build_manual_import_payload_with_series("IDW Publishing", "tmnt"),
        headers=auth_headers(token),
    )

    assert import_response.status_code == 201
    data = import_response.json()
    assert data["needs_metadata_review"] is False
    assert data["parsed_payload_json"]["items"][0]["title"] == "Teenage Mutant Ninja Turtles"


def test_publisher_aliases_still_work_with_series_alias_support(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops@example.com")

    create_publisher_alias = client.post(
        "/ops/metadata-aliases",
        json={
            "alias_value": "Boom! Studios",
            "canonical_value": "BOOM!",
            "alias_type": "publisher",
        },
        headers=auth_headers(token),
    )
    assert create_publisher_alias.status_code == 201

    import_response = client.post(
        "/imports/manual",
        json=build_manual_import_payload_with_series(
            "Boom! Studios",
            "Something Is Killing the Children",
        ),
        headers=auth_headers(token),
    )

    assert import_response.status_code == 201
    item = import_response.json()["parsed_payload_json"]["items"][0]
    assert item["publisher"] == "BOOM!"


def test_creator_alias_creation_updates_future_draft_enrichment(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops@example.com")

    create_alias = client.post(
        "/ops/metadata-aliases",
        json={
            "alias_value": "Joshua Cassara",
            "canonical_value": "Josh Cassara",
            "alias_type": "creator",
        },
        headers=auth_headers(token),
    )
    assert create_alias.status_code == 201

    creators_only = client.get(
        "/ops/metadata-aliases?alias_type=creator",
        headers=auth_headers(token),
    )
    assert creators_only.status_code == 200
    assert any(alias["alias_type"] == "creator" for alias in creators_only.json())

    manual_import = client.post(
        "/imports/manual",
        json={
            **build_manual_import_payload("Marvel"),
            "items": [
                {
                    **build_manual_import_payload("Marvel")["items"][0],
                    "writers": ["Joshua Cassara"],
                }
            ],
        },
        headers=auth_headers(token),
    )
    assert manual_import.status_code == 201
    item = manual_import.json()["parsed_payload_json"]["items"][0]
    assert item["writers"] == ["Josh Cassara"]
    assert manual_import.json()["needs_metadata_review"] is False

    normalized = normalize_creator_name("Joshua Cassara")
    assert normalized.normalized_value == "joshua cassara"
